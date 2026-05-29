import re
from collections.abc import Callable
from dataclasses import asdict
from html import escape
from html.parser import HTMLParser
from typing import Any

from bs4 import BeautifulSoup

from .errors import ErrorCode, ReportEngineError
from .llm import LlmAdapter
from .models import DatasetContext, Stage2Component, TemplateContext
from .prompt_store import PromptStore


Stage3AttemptRecorder = Callable[[dict[str, Any]], None]


class Stage3LayoutService:
    def __init__(self, llm_adapter: LlmAdapter, prompt_store: PromptStore | None = None):
        self.llm_adapter = llm_adapter
        self.prompt_store = prompt_store or PromptStore()

    def build_prompt_input(
        self,
        template_context: TemplateContext,
        dataset: DatasetContext,
        month_snapshot: dict[str, Any],
        components: list[Stage2Component],
    ) -> dict[str, Any]:
        return {
            "template": asdict(template_context),
            "dataset": {
                "datasetId": dataset.datasetId,
                "productName": dataset.baseData["product"]["productName"],
                "distributorName": dataset.baseData["salesChannel"]["distributorName"],
            },
            "monthSnapshot": {
                "monthId": month_snapshot["monthId"],
                "asOf": month_snapshot["asOf"],
                "periodLabel": month_snapshot["periodLabel"],
            },
            "components": [
                {
                    "componentId": component.componentId,
                    "componentKey": component.componentKey,
                    "renderType": component.renderType,
                    "html": stage3_component_html(component),
                    "chartDeferredToStage4": _is_chart_component(component),
                }
                for component in components
            ],
            "visualObjective": self._read_prompt_list("03_layout_visual_objective.json"),
            "constraints": self._read_prompt_list("03_layout_constraints.json"),
        }

    def generate_report_draft(
        self,
        prompt_input: dict[str, Any],
        components: list[Stage2Component],
        template_image_data_url: str | None = None,
        max_correction_attempts: int = 3,
        attempt_recorder: Stage3AttemptRecorder | None = None,
    ) -> str:
        if max_correction_attempts < 0:
            raise ReportEngineError(
                ErrorCode.CONFIG_INVALID,
                "max_correction_attempts must be zero or greater",
                stage="stage3",
            )

        attempts: list[dict[str, Any]] = []
        current_prompt_input = prompt_input
        for attempt_number in range(max_correction_attempts + 1):
            html = self._generate_layout_html(current_prompt_input, template_image_data_url)
            try:
                self.validate_report_draft(html, components, prompt_input=current_prompt_input)
            except ReportEngineError as exc:
                if exc.code != ErrorCode.LAYOUT_GENERATION_INVALID:
                    raise
                attempt = _stage3_attempt_record(attempt_number, "failed", html, components, exc)
                attempts.append(attempt)
                _record_stage3_attempt(attempt_recorder, attempt)
                if attempt_number >= max_correction_attempts:
                    repaired = _repair_source_fragment_violations(html, components)
                    if repaired is not None:
                        repaired_html, repair_payload = repaired
                        try:
                            self.validate_report_draft(repaired_html, components, prompt_input=current_prompt_input)
                        except ReportEngineError as repair_exc:
                            repair_attempt = _stage3_attempt_record(
                                attempt_number + 1,
                                "failed",
                                repaired_html,
                                components,
                                repair_exc,
                                phase="local_repair",
                            )
                            repair_attempt["localRepair"] = repair_payload
                            attempts.append(repair_attempt)
                            _record_stage3_attempt(attempt_recorder, repair_attempt)
                            setattr(
                                repair_exc,
                                "stage3_validation_loop",
                                _stage3_validation_loop_payload(max_correction_attempts, attempts),
                            )
                            raise repair_exc
                        repair_attempt = _stage3_attempt_record(
                            attempt_number + 1,
                            "passed",
                            repaired_html,
                            components,
                            None,
                            phase="local_repair",
                        )
                        repair_attempt["localRepair"] = repair_payload
                        attempts.append(repair_attempt)
                        _record_stage3_attempt(attempt_recorder, repair_attempt)
                        return repaired_html
                    setattr(
                        exc,
                        "stage3_validation_loop",
                        _stage3_validation_loop_payload(max_correction_attempts, attempts),
                    )
                    raise
                current_prompt_input = self._build_correction_prompt_input(
                    prompt_input,
                    html,
                    exc,
                    components,
                    attempt=attempt_number + 1,
                    previous_attempts=attempts,
                )
                continue

            attempt = _stage3_attempt_record(attempt_number, "passed", html, components, None)
            attempts.append(attempt)
            _record_stage3_attempt(attempt_recorder, attempt)
            return html

        raise self._invalid("Stage 3 layout validation loop ended without a result")

    def validate_report_draft(
        self,
        html: str,
        components: list[Stage2Component],
        *,
        prompt_input: dict[str, Any] | None = None,
    ) -> None:
        if not isinstance(html, str) or not html.strip():
            raise self._invalid("Stage 3 layout output must be non-empty HTML")
        lowered = html.lstrip().lower()
        if not lowered.startswith("<!doctype html>") or "<html" not in lowered:
            raise self._invalid("Stage 3 layout output must be a complete HTML document")
        if not _has_document_local_css(html):
            raise self._invalid("Stage 3 layout output must include document-local CSS in a non-empty <style> block")
        if _EXTERNAL_RESOURCE_PATTERN.search(html):
            raise self._invalid("Stage 3 layout output must not reference external CSS or network resources")
        missing_css_variables = _missing_template_css_variables(html)
        if missing_css_variables:
            raise self._invalid(
                "Stage 3 layout output must define template-derived CSS variables: "
                + ", ".join(missing_css_variables)
            )
        missing = [
            component.componentId
            for component in components
            if not _has_stage3_component_marker(html, component)
        ]
        if missing:
            raise self._invalid(f"Stage 3 layout output is missing components: {', '.join(missing)}")
        if _has_forbidden_chart_rendering(html, components):
            raise self._invalid("Stage 3 layout output must not render charts before Stage 4")
        if _has_footer_overlap_risk(html):
            raise self._invalid("Stage 3 layout output must keep footer in normal document flow")
        self._validate_template_revision_safety(html, prompt_input)
        invalid_placeholders = [
            f"{component.componentId} ({_chart_placeholder_count(html, component.componentId)})"
            for component in components
            if _is_chart_component(component) and _chart_placeholder_count(html, component.componentId) != 1
        ]
        if invalid_placeholders:
            raise self._invalid(
                "Stage 3 layout output must include chart placeholders: exactly one chart placeholder "
                "for each chart component: "
                + ", ".join(invalid_placeholders)
            )
        self._validate_source_fragments_preserved(html, components)

    def _generate_layout_html(self, prompt_input: dict[str, Any], template_image_data_url: str | None) -> str:
        return self._normalize_html(
            self.llm_adapter.generate_stage3_layout(
                prompt_input,
                template_image_data_url=template_image_data_url,
            )
        )

    def _build_correction_prompt_input(
        self,
        prompt_input: dict[str, Any],
        rejected_html: str,
        error: ReportEngineError,
        components: list[Stage2Component],
        *,
        attempt: int = 1,
        previous_attempts: list[dict[str, Any]] | None = None,
    ) -> dict[str, Any]:
        source_fragment_violations = _source_fragment_violations(rejected_html, components)
        previous_attempts = previous_attempts or []
        repeated_fragments = _repeated_missing_fragments(previous_attempts)
        requirements = self._read_prompt_list("03_layout_correction_requirements.json")
        if _is_footer_flow_error(error):
            requirements = [
                *requirements,
                "Remove position:absolute and position:fixed from footer, .footer, #footer, and bottom disclaimer CSS.",
                "Do not anchor footer or bottom disclaimers with bottom/left/right overlay coordinates.",
                "Do not rely on main padding-bottom or page overflow:hidden to make room for an absolutely positioned footer.",
                "Rewrite forbidden footer CSS from rejectedHtml instead of copying it.",
                "Place footer after main content as normal-flow block content; static or relative positioning is acceptable.",
            ]
        if _is_template_css_variable_error(error):
            requirements = [
                *requirements,
                "Infer --report-primary, --report-accent, --chart-series-1, and --chart-series-2 from the attached template preview image.",
                "Define those CSS variables in document-local CSS before using them.",
                "Do not use supplied JSON color values or a generic blue palette for these CSS variables.",
            ]
        if source_fragment_violations:
            requirements = [
                *requirements,
                "Render every sourceFragmentViolations.missingFragments item exactly as visible text in the corrected HTML.",
                "Do not remove sign prefixes, percent symbols, currency or unit symbols, commas, or decimal points.",
                "Do not move unit symbols from table cells into a separate footnote when the source table cells include them.",
                "Do not normalize visible date formats, spacing, punctuation, or Korean/English date notation from source HTML.",
            ]
        if repeated_fragments:
            requirements = [
                *requirements,
                "strictLiteralPreservation is true because the same source fragments were missed in earlier attempts.",
                "Render every mustRenderFragments item byte-for-byte as visible text in the corrected HTML.",
            ]
        return {
            **prompt_input,
            "correction": {
                "attempt": attempt,
                "previousError": str(error),
                "requirements": requirements,
                "sourceFragmentViolations": source_fragment_violations,
                "previousAttempts": [_stage3_attempt_prompt_payload(item) for item in previous_attempts],
                "strictLiteralPreservation": bool(repeated_fragments),
                "mustRenderFragments": repeated_fragments,
                "rejectedHtml": rejected_html,
            },
        }

    def _validate_source_fragments_preserved(self, html: str, components: list[Stage2Component]) -> None:
        violations = _source_fragment_violations(html, components)
        missing_by_component = [
            f"{violation['componentId']}: {', '.join(violation['missingFragments'][:3])}"
            for violation in violations
        ]
        if missing_by_component:
            raise self._invalid(
                "Stage 3 layout output changed or omitted source fragments: "
                + "; ".join(missing_by_component[:5])
            )

    def _validate_template_revision_safety(self, html: str, prompt_input: dict[str, Any] | None) -> None:
        revision_profile = _revision_profile(prompt_input)
        verification_correction = _verification_correction(prompt_input)
        if not revision_profile or not verification_correction:
            return
        if verification_correction.get("revisionMode") != "minimal_patch":
            return

        forbidden_tokens = revision_profile.get("forbiddenCssTokens")
        if not isinstance(forbidden_tokens, list):
            return
        lowered = html.lower()
        matched_tokens = [
            token
            for token in forbidden_tokens
            if isinstance(token, str)
            and token.strip()
            and _matches_forbidden_revision_token(lowered, token.strip().lower())
        ]
        if matched_tokens:
            raise self._invalid(
                "Woori revision safety rejected unsafe layout patterns: "
                + ", ".join(matched_tokens[:5])
            )

    def _invalid(self, detail: str) -> ReportEngineError:
        return ReportEngineError(ErrorCode.LAYOUT_GENERATION_INVALID, detail, stage="stage3")

    def _read_prompt_list(self, filename: str) -> list[str]:
        value = self.prompt_store.read_json(filename)
        if not isinstance(value, list) or not value or not all(isinstance(item, str) and item.strip() for item in value):
            raise ReportEngineError(
                ErrorCode.CONFIG_INVALID,
                f"Prompt JSON file must be a non-empty list of strings: {filename}",
                stage="prompt",
            )
        return value

    @staticmethod
    def _normalize_html(raw_html: str) -> str:
        html = raw_html.strip()
        fenced = re.search(r"```(?:html)?\s*(.*?)\s*```", html, flags=re.IGNORECASE | re.DOTALL)
        if fenced:
            html = fenced.group(1).strip()

        lower_html = html.lower()
        doctype_index = lower_html.find("<!doctype html>")
        if doctype_index >= 0:
            return html[doctype_index:].strip()

        html_index = lower_html.find("<html")
        if html_index >= 0:
            return "<!doctype html>\n" + html[html_index:].strip()
        return html


_GLOBAL_CHART_RENDER_PATTERN = re.compile(
    r"(<canvas\b|<script\b|new\s+Chart\s*\(|chart\.js|chartjs)",
    re.IGNORECASE,
)
_FOOTER_INLINE_POSITION_PATTERN = re.compile(
    r"<footer\b[^>]*style\s*=\s*(['\"])[^'\"]*position\s*:\s*(?:absolute|fixed)\b",
    re.IGNORECASE | re.DOTALL,
)
_CSS_RULE_PATTERN = re.compile(r"([^{}]+)\{([^{}]*)\}", re.DOTALL)
_CSS_COMMENT_PATTERN = re.compile(r"/\*.*?\*/", re.DOTALL)
_FORBIDDEN_POSITION_PATTERN = re.compile(r"\bposition\s*:\s*(?:absolute|fixed)\b", re.IGNORECASE)
_FOOTER_TAG_SELECTOR_PATTERN = re.compile(r"(^|[\s>+~])footer(?=$|[\s.#:\[>+~])", re.IGNORECASE)
_FOOTER_CLASS_SELECTOR_PATTERN = re.compile(r"(^|[\s>+~])\.footer(?=$|[\s.#:\[>+~])", re.IGNORECASE)
_FOOTER_ID_SELECTOR_PATTERN = re.compile(r"(^|[\s>+~])#footer(?=$|[\s.#:\[>+~])", re.IGNORECASE)
_STYLE_BLOCK_PATTERN = re.compile(r"<style\b[^>]*>(.*?)</style>", re.IGNORECASE | re.DOTALL)
_EXTERNAL_RESOURCE_PATTERN = re.compile(
    r"("
    r"<link\b(?=[^>]*\brel\s*=\s*['\"]?stylesheet\b)"
    r"|@import\b"
    r"|(?:href|src)\s*=\s*['\"]?\s*(?:https?:)?//"
    r"|url\(\s*['\"]?\s*(?:https?:)?//"
    r")",
    re.IGNORECASE | re.DOTALL,
)
_REQUIRED_TEMPLATE_CSS_VARIABLES = (
    "--report-primary",
    "--report-accent",
    "--chart-series-1",
    "--chart-series-2",
)


def stage3_component_html(component: Stage2Component) -> str:
    if _is_chart_component(component):
        component_id = escape(component.componentId, quote=True)
        return (
            f'<section data-component-id="{component_id}">'
            f'<div data-chart-placeholder="{component_id}"></div>'
            "</section>"
        )
    return component.html


def _stage3_attempt_record(
    attempt: int,
    status: str,
    html: str,
    components: list[Stage2Component],
    error: ReportEngineError | None,
    *,
    phase: str | None = None,
) -> dict[str, Any]:
    record: dict[str, Any] = {
        "attempt": attempt,
        "phase": phase or ("initial" if attempt == 0 else "correction"),
        "status": status,
        "html": html,
        "htmlChars": len(html),
        "sourceFragmentViolations": _source_fragment_violations(html, components),
    }
    if error is not None:
        record["error"] = str(error)
        record["errorCode"] = error.code.value
    return record


def _record_stage3_attempt(attempt_recorder: Stage3AttemptRecorder | None, attempt: dict[str, Any]) -> None:
    if attempt_recorder is not None:
        attempt_recorder(attempt)


def _stage3_validation_loop_payload(
    max_correction_attempts: int,
    attempts: list[dict[str, Any]],
) -> dict[str, Any]:
    return {
        "maxCorrectionAttempts": max_correction_attempts,
        "attemptCount": len(attempts),
        "passed": bool(attempts and attempts[-1].get("status") == "passed"),
        "attempts": [_stage3_attempt_log_payload(attempt) for attempt in attempts],
    }


def _stage3_attempt_log_payload(attempt: dict[str, Any]) -> dict[str, Any]:
    return {key: value for key, value in attempt.items() if key != "html"}


def _stage3_attempt_prompt_payload(attempt: dict[str, Any]) -> dict[str, Any]:
    payload = _stage3_attempt_log_payload(attempt)
    return {
        key: payload[key]
        for key in ("attempt", "phase", "status", "htmlChars", "errorCode", "error", "sourceFragmentViolations")
        if key in payload
    }


def _repeated_missing_fragments(attempts: list[dict[str, Any]]) -> list[str]:
    counts: dict[str, int] = {}
    ordered: list[str] = []
    for attempt in attempts:
        for violation in attempt.get("sourceFragmentViolations", []):
            if not isinstance(violation, dict):
                continue
            missing_fragments = violation.get("missingFragments")
            if not isinstance(missing_fragments, list):
                continue
            for fragment in missing_fragments:
                if not isinstance(fragment, str) or not fragment:
                    continue
                if fragment not in counts:
                    ordered.append(fragment)
                counts[fragment] = counts.get(fragment, 0) + 1
    return [fragment for fragment in ordered if counts.get(fragment, 0) >= 2]


def _matches_forbidden_revision_token(lowered_html: str, token: str) -> bool:
    if token.endswith(":"):
        property_name = token[:-1].strip()
        if not property_name:
            return False
        return re.search(rf"(?<![-\w]){re.escape(property_name)}\s*:", lowered_html) is not None
    return token in lowered_html


def _is_chart_component(component: Stage2Component) -> bool:
    return component.renderType == "chart" or component.chartSpec is not None


def _has_chart_placeholder(html: str, component_id: str) -> bool:
    return _chart_placeholder_count(html, component_id) > 0


def _chart_placeholder_count(html: str, component_id: str) -> int:
    return _html_attribute_count(html, "data-chart-placeholder", component_id)


def _has_component_id_marker(html: str, component_id: str) -> bool:
    return _html_attribute_count(html, "data-component-id", component_id) > 0


def _has_stage3_component_marker(html: str, component: Stage2Component) -> bool:
    if _has_component_id_marker(html, component.componentId):
        return True
    return _is_chart_component(component) and _has_chart_placeholder(html, component.componentId)


def _has_document_local_css(html: str) -> bool:
    for match in _STYLE_BLOCK_PATTERN.finditer(html):
        if match.group(1).strip():
            return True
    return False


def _missing_template_css_variables(html: str) -> list[str]:
    css = "\n".join(match.group(1) for match in _STYLE_BLOCK_PATTERN.finditer(html))
    return [name for name in _REQUIRED_TEMPLATE_CSS_VARIABLES if not re.search(rf"{re.escape(name)}\s*:", css)]


def _has_footer_overlap_risk(html: str) -> bool:
    if _FOOTER_INLINE_POSITION_PATTERN.search(html):
        return True
    for style_match in _STYLE_BLOCK_PATTERN.finditer(html):
        css = _CSS_COMMENT_PATTERN.sub("", style_match.group(1))
        for rule_match in _CSS_RULE_PATTERN.finditer(css):
            selectors, declarations = rule_match.groups()
            if not _FORBIDDEN_POSITION_PATTERN.search(declarations):
                continue
            if any(_selector_targets_footer(selector.strip()) for selector in selectors.split(",")):
                return True
    return False


def _selector_targets_footer(selector: str) -> bool:
    return bool(
        _FOOTER_TAG_SELECTOR_PATTERN.search(selector)
        or _FOOTER_CLASS_SELECTOR_PATTERN.search(selector)
        or _FOOTER_ID_SELECTOR_PATTERN.search(selector)
    )


def _is_footer_flow_error(error: Exception) -> bool:
    message = str(error).lower()
    return "footer" in message and "normal document flow" in message


def _is_template_css_variable_error(error: Exception) -> bool:
    return "template-derived css variables" in str(error).lower()


def _revision_profile(prompt_input: dict[str, Any] | None) -> dict[str, Any] | None:
    if not isinstance(prompt_input, dict):
        return None
    template = prompt_input.get("template")
    if not isinstance(template, dict):
        return None
    profile = template.get("revisionProfile")
    return profile if isinstance(profile, dict) else None


def _verification_correction(prompt_input: dict[str, Any] | None) -> dict[str, Any] | None:
    if not isinstance(prompt_input, dict):
        return None
    correction = prompt_input.get("verificationCorrection")
    return correction if isinstance(correction, dict) else None


def _has_forbidden_chart_rendering(html: str, components: list[Stage2Component]) -> bool:
    if _GLOBAL_CHART_RENDER_PATTERN.search(html):
        return True
    chart_component_ids = {component.componentId for component in components if _is_chart_component(component)}
    if not chart_component_ids:
        return False
    parser = _ChartSvgRenderParser(chart_component_ids)
    parser.feed(html)
    parser.close()
    return parser.found


def _source_fragments(html: str) -> list[str]:
    fragments: list[str] = []
    for fragment in _extract_preserved_source_fragments(html):
        normalized = _normalize_preserved_source_fragment(fragment)
        if normalized:
            fragments.append(normalized)
    return fragments


def _source_fragment_violations(html: str, components: list[Stage2Component]) -> list[dict[str, Any]]:
    document_text = _normalize_text(" ".join(_extract_text_fragments(html)))
    violations: list[dict[str, Any]] = []
    for component in components:
        if _is_chart_component(component):
            continue
        missing_fragments = [
            fragment
            for fragment in _source_fragments(component.html)
            if fragment not in document_text
        ]
        if missing_fragments:
            violations.append(
                {
                    "componentId": component.componentId,
                    "componentKey": component.componentKey,
                    "missingFragments": missing_fragments,
                }
            )
    return violations


def _repair_source_fragment_violations(
    html: str,
    components: list[Stage2Component],
) -> tuple[str, dict[str, Any]] | None:
    violations = _source_fragment_violations(html, components)
    if not violations:
        return None

    components_by_id = {component.componentId: component for component in components}
    soup = BeautifulSoup(html, "html.parser")
    repaired_components: list[dict[str, Any]] = []
    for violation in violations:
        component_id = violation.get("componentId")
        if not isinstance(component_id, str):
            continue
        component = components_by_id.get(component_id)
        if component is None or _is_chart_component(component):
            continue

        source_soup = BeautifulSoup(component.html, "html.parser")
        source_node = source_soup.find(attrs={"data-component-id": component_id})
        target_node = soup.find(attrs={"data-component-id": component_id})
        if source_node is None or target_node is None:
            continue

        target_node.clear()
        for child in list(source_node.contents):
            target_node.append(child)
        repaired_components.append(
            {
                "componentId": component.componentId,
                "componentKey": component.componentKey,
                "missingFragments": violation.get("missingFragments", []),
            }
        )

    if not repaired_components:
        return None
    return (
        str(soup),
        {
            "type": "source_fragment_restore",
            "strategy": "replace_component_inner_html",
            "repairedComponents": repaired_components,
        },
    )


def _extract_text_fragments(html: str) -> list[str]:
    parser = _TextFragmentParser()
    parser.feed(html)
    parser.close()
    return parser.fragments


def _normalize_text(text: str) -> str:
    return " ".join(text.split())


def _normalize_preserved_source_fragment(text: str) -> str:
    normalized = _normalize_text(text)
    return re.sub(
        r"^(?:[①②③④⑤⑥⑦⑧⑨⑩⑪⑫⑬⑭⑮⑯⑰⑱⑲⑳]|[0-9]+[.)])\s+",
        "",
        normalized,
    )


def _html_attribute_count(html: str, attribute_name: str, attribute_value: str) -> int:
    parser = _HtmlAttributeCounter(attribute_name, attribute_value)
    parser.feed(html)
    parser.close()
    return parser.count


class _HtmlAttributeCounter(HTMLParser):
    def __init__(self, attribute_name: str, attribute_value: str):
        super().__init__(convert_charrefs=True)
        self.attribute_name = attribute_name.lower()
        self.attribute_value = attribute_value
        self.count = 0
        self._ignored_depth = 0

    def handle_starttag(self, tag: str, attrs) -> None:
        normalized_tag = tag.lower()
        if normalized_tag in {"script", "style"}:
            self._ignored_depth += 1
            return
        if self._ignored_depth:
            return
        self._count_attrs(attrs)

    def handle_startendtag(self, tag: str, attrs) -> None:
        if self._ignored_depth or tag.lower() in {"script", "style"}:
            return
        self._count_attrs(attrs)

    def handle_endtag(self, tag: str) -> None:
        if tag.lower() in {"script", "style"} and self._ignored_depth > 0:
            self._ignored_depth -= 1

    def _count_attrs(self, attrs) -> None:
        for name, value in attrs:
            if name.lower() == self.attribute_name and value == self.attribute_value:
                self.count += 1


class _ChartSvgRenderParser(HTMLParser):
    _VOID_TAGS = {
        "area",
        "base",
        "br",
        "col",
        "embed",
        "hr",
        "img",
        "input",
        "link",
        "meta",
        "param",
        "source",
        "track",
        "wbr",
    }

    def __init__(self, chart_component_ids: set[str]):
        super().__init__(convert_charrefs=True)
        self.chart_component_ids = chart_component_ids
        self.found = False
        self._chart_scope_depth = 0
        self._stack: list[tuple[str, bool]] = []

    def handle_starttag(self, tag: str, attrs) -> None:
        normalized_tag = tag.lower()
        is_chart_scope = self._is_chart_scope(attrs)
        if self._is_forbidden_svg(normalized_tag, attrs, is_chart_scope):
            self.found = True
        if normalized_tag not in self._VOID_TAGS:
            self._stack.append((normalized_tag, is_chart_scope))
            if is_chart_scope:
                self._chart_scope_depth += 1

    def handle_startendtag(self, tag: str, attrs) -> None:
        normalized_tag = tag.lower()
        is_chart_scope = self._is_chart_scope(attrs)
        if self._is_forbidden_svg(normalized_tag, attrs, is_chart_scope):
            self.found = True

    def handle_endtag(self, tag: str) -> None:
        normalized_tag = tag.lower()
        while self._stack:
            open_tag, is_chart_scope = self._stack.pop()
            if is_chart_scope:
                self._chart_scope_depth -= 1
            if open_tag == normalized_tag:
                break

    def _is_forbidden_svg(self, tag: str, attrs, is_chart_scope: bool) -> bool:
        if tag != "svg":
            return False
        if _has_attribute(attrs, "data-chart-rendered"):
            return True
        return self._chart_scope_depth > 0 or is_chart_scope

    def _is_chart_scope(self, attrs) -> bool:
        return _has_attribute_value(attrs, "data-component-id", self.chart_component_ids) or _has_attribute_value(
            attrs,
            "data-chart-placeholder",
            self.chart_component_ids,
        )


def _has_attribute(attrs, attribute_name: str) -> bool:
    normalized_attribute_name = attribute_name.lower()
    return any(name.lower() == normalized_attribute_name for name, _ in attrs)


def _has_attribute_value(attrs, attribute_name: str, values: set[str]) -> bool:
    normalized_attribute_name = attribute_name.lower()
    return any(name.lower() == normalized_attribute_name and value in values for name, value in attrs)


class _TextFragmentParser(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.fragments: list[str] = []
        self._ignored_depth = 0

    def handle_starttag(self, tag: str, attrs) -> None:
        if tag.lower() in {"script", "style"}:
            self._ignored_depth += 1

    def handle_endtag(self, tag: str) -> None:
        if tag.lower() in {"script", "style"} and self._ignored_depth > 0:
            self._ignored_depth -= 1

    def handle_data(self, data: str) -> None:
        if self._ignored_depth:
            return
        normalized = _normalize_text(data)
        if normalized:
            self.fragments.append(normalized)


def _extract_preserved_source_fragments(html: str) -> list[str]:
    parser = _SourcePreservationFragmentParser()
    parser.feed(html)
    parser.close()
    return parser.fragments


class _SourcePreservationFragmentParser(HTMLParser):
    _TARGET_TAGS = {"th", "td", "li", "p"}

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.fragments: list[str] = []
        self._ignored_depth = 0
        self._captures: list[dict[str, Any]] = []

    def handle_starttag(self, tag: str, attrs) -> None:
        normalized_tag = tag.lower()
        if normalized_tag in {"script", "style"}:
            self._ignored_depth += 1
            return
        if self._ignored_depth:
            return
        if normalized_tag in self._TARGET_TAGS:
            self._captures.append({"tag": normalized_tag, "parts": []})

    def handle_endtag(self, tag: str) -> None:
        normalized_tag = tag.lower()
        if normalized_tag in {"script", "style"} and self._ignored_depth > 0:
            self._ignored_depth -= 1
            return
        if self._ignored_depth or not self._captures:
            return
        capture = self._captures[-1]
        if capture["tag"] != normalized_tag:
            return
        self._captures.pop()
        normalized = _normalize_text(" ".join(capture["parts"]))
        if normalized:
            self.fragments.append(normalized)

    def handle_data(self, data: str) -> None:
        if self._ignored_depth:
            return
        normalized = _normalize_text(data)
        if not normalized:
            return
        for capture in self._captures:
            capture["parts"].append(normalized)
