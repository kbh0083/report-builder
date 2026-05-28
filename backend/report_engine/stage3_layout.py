import re
from dataclasses import asdict
from html import escape
from html.parser import HTMLParser
from typing import Any

from .errors import ErrorCode, ReportEngineError
from .llm import LlmAdapter
from .models import DatasetContext, Stage2Component, TemplateContext
from .prompt_store import PromptStore


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
                "styleCandidates": dataset.styleCandidates or {},
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
    ) -> str:
        html = self._generate_layout_html(prompt_input, template_image_data_url)
        try:
            self.validate_report_draft(html, components)
        except ReportEngineError as exc:
            if exc.code != ErrorCode.LAYOUT_GENERATION_INVALID:
                raise
            correction_input = self._build_correction_prompt_input(prompt_input, html, exc)
            html = self._generate_layout_html(correction_input, template_image_data_url)
            self.validate_report_draft(html, components)
        return html

    def validate_report_draft(self, html: str, components: list[Stage2Component]) -> None:
        if not isinstance(html, str) or not html.strip():
            raise self._invalid("Stage 3 layout output must be non-empty HTML")
        lowered = html.lstrip().lower()
        if not lowered.startswith("<!doctype html>") or "<html" not in lowered:
            raise self._invalid("Stage 3 layout output must be a complete HTML document")
        if not _has_document_local_css(html):
            raise self._invalid("Stage 3 layout output must include document-local CSS in a non-empty <style> block")
        if _EXTERNAL_RESOURCE_PATTERN.search(html):
            raise self._invalid("Stage 3 layout output must not reference external CSS or network resources")
        missing = [
            component.componentId
            for component in components
            if not _has_stage3_component_marker(html, component)
        ]
        if missing:
            raise self._invalid(f"Stage 3 layout output is missing components: {', '.join(missing)}")
        if _has_forbidden_chart_rendering(html, components):
            raise self._invalid("Stage 3 layout output must not render charts before Stage 4")
        if _FOOTER_OVERLAP_RISK_PATTERN.search(html):
            raise self._invalid("Stage 3 layout output must keep footer in normal document flow")
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
    ) -> dict[str, Any]:
        return {
            **prompt_input,
            "correction": {
                "attempt": 1,
                "previousError": str(error),
                "requirements": self._read_prompt_list("03_layout_correction_requirements.json"),
                "rejectedHtml": rejected_html,
            },
        }

    def _validate_source_fragments_preserved(self, html: str, components: list[Stage2Component]) -> None:
        document_text = _normalize_text(" ".join(_extract_text_fragments(html)))
        missing_by_component: list[str] = []
        for component in components:
            if _is_chart_component(component):
                continue
            missing_fragments = [
                fragment
                for fragment in _source_fragments(component.html)
                if fragment not in document_text
            ]
            if missing_fragments:
                preview = ", ".join(missing_fragments[:3])
                missing_by_component.append(f"{component.componentId}: {preview}")
        if missing_by_component:
            raise self._invalid(
                "Stage 3 layout output changed or omitted source fragments: "
                + "; ".join(missing_by_component[:5])
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
_FOOTER_OVERLAP_RISK_PATTERN = re.compile(
    r"("
    r"(?:footer|\.footer|#footer)[^{]*\{[^}]*position\s*:\s*(?:absolute|fixed)\b"
    r"|<footer\b[^>]*style\s*=\s*['\"][^'\"]*position\s*:\s*(?:absolute|fixed)\b"
    r")",
    re.IGNORECASE | re.DOTALL,
)
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


def stage3_component_html(component: Stage2Component) -> str:
    if _is_chart_component(component):
        component_id = escape(component.componentId, quote=True)
        return (
            f'<section data-component-id="{component_id}">'
            f'<div data-chart-placeholder="{component_id}"></div>'
            "</section>"
        )
    return component.html


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
