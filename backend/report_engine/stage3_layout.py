import re
from dataclasses import asdict
from html import escape
from typing import Any

from .errors import ErrorCode, ReportEngineError
from .llm import LlmAdapter
from .models import DatasetContext, Stage2Component, TemplateContext


class Stage3LayoutService:
    def __init__(self, llm_adapter: LlmAdapter):
        self.llm_adapter = llm_adapter

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
            "constraints": [
                "Return one complete HTML document.",
                "Preserve every Stage 2 component id.",
                "Do not change source numbers or source wording.",
                "Do not reference external network resources.",
                "Do not render charts in Stage 3.",
                "Keep chart components as data-chart-placeholder containers only; Stage 4 renders chart assets.",
                "Do not create SVG, canvas, script, Chart.js, or other chart rendering markup.",
                "Footer must stay in normal document flow.",
                "Do not use position:absolute or position:fixed for footer or bottom disclaimers.",
                "Reserve a bottom safe area so the final section never overlaps the footer.",
                "If content is long, reduce spacing or continue the normal page flow instead of overlapping footer text.",
            ],
        }

    def generate_report_draft(self, prompt_input: dict[str, Any], components: list[Stage2Component]) -> str:
        html = self._normalize_html(self.llm_adapter.generate_stage3_layout(prompt_input))
        self.validate_report_draft(html, components)
        return html

    def validate_report_draft(self, html: str, components: list[Stage2Component]) -> None:
        if not isinstance(html, str) or not html.strip():
            raise self._invalid("Stage 3 layout output must be non-empty HTML")
        lowered = html.lstrip().lower()
        if not lowered.startswith("<!doctype html>") or "<html" not in lowered:
            raise self._invalid("Stage 3 layout output must be a complete HTML document")
        missing = [component.componentId for component in components if component.componentId not in html]
        if missing:
            raise self._invalid(f"Stage 3 layout output is missing components: {', '.join(missing)}")
        if _CHART_RENDER_PATTERN.search(html):
            raise self._invalid("Stage 3 layout output must not render charts before Stage 4")
        if _FOOTER_OVERLAP_RISK_PATTERN.search(html):
            raise self._invalid("Stage 3 layout output must keep footer in normal document flow")
        missing_placeholders = [
            component.componentId
            for component in components
            if _is_chart_component(component) and not _has_chart_placeholder(html, component.componentId)
        ]
        if missing_placeholders:
            raise self._invalid(f"Stage 3 layout output is missing chart placeholders: {', '.join(missing_placeholders)}")

    def _invalid(self, detail: str) -> ReportEngineError:
        return ReportEngineError(ErrorCode.LAYOUT_GENERATION_INVALID, detail, stage="stage3")

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


_CHART_RENDER_PATTERN = re.compile(
    r"(<canvas\b|<svg\b|<script\b|new\s+Chart\s*\(|chart\.js|chartjs)",
    re.IGNORECASE,
)
_FOOTER_OVERLAP_RISK_PATTERN = re.compile(
    r"("
    r"(?:footer|\.footer|#footer)[^{]*\{[^}]*position\s*:\s*(?:absolute|fixed)\b"
    r"|<footer\b[^>]*style\s*=\s*['\"][^'\"]*position\s*:\s*(?:absolute|fixed)\b"
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
    marker = re.escape(component_id)
    pattern = rf"data-chart-placeholder\s*=\s*['\"]{marker}['\"]"
    return re.search(pattern, html) is not None
