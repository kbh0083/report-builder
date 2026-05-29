import math
import re
from html import escape
from typing import Any

from .errors import ErrorCode, ReportEngineError
from .models import Stage2Component, TemplateContext


class ChartRenderer:
    """Render Stage 2 chartSpec data and inject it into the Stage 3 placeholder."""

    def render_and_inject(
        self,
        html: str,
        components: list[Stage2Component],
        *,
        template_context: TemplateContext | None = None,
    ) -> str:
        component = self._performance_chart_component(components)
        spec = self._validate_chart_spec(component.chartSpec)
        colors = _chart_series_colors(html)
        effective_type, _ = self._effective_chart_type(spec, template_context)
        svg = self._render_line_svg(spec, colors) if effective_type == "line" else self._render_bar_svg(spec, colors)
        return self._replace_placeholder(html, component.componentId, svg)

    def describe_chart_rendering(
        self,
        components: list[Stage2Component],
        *,
        template_context: TemplateContext | None = None,
    ) -> dict[str, str]:
        component = self._performance_chart_component(components)
        spec = self._validate_chart_spec(component.chartSpec)
        effective_type, source = self._effective_chart_type(spec, template_context)
        return {
            "originalChartSpecType": spec["type"],
            "effectiveChartType": effective_type,
            "chartTypeSource": source,
        }

    def _performance_chart_component(self, components: list[Stage2Component]) -> Stage2Component:
        charts = [component for component in components if component.componentKey == "performance_chart"]
        if len(charts) != 1:
            raise self._render_failed("Stage 4 requires exactly one performance_chart component")
        if not charts[0].chartSpec:
            raise self._render_failed("performance_chart must include chartSpec")
        return charts[0]

    def _validate_chart_spec(self, chart_spec: dict[str, Any] | None) -> dict[str, Any]:
        if not isinstance(chart_spec, dict):
            raise self._render_failed("chartSpec must be an object")
        chart_type = chart_spec.get("type")
        if chart_type not in {"bar", "line"}:
            raise self._render_failed("Only bar and line chartSpec types are supported")

        labels = chart_spec.get("labels")
        if not isinstance(labels, list) or not labels:
            raise self._render_failed("chartSpec.labels must be a non-empty list")
        normalized_labels = [str(label) for label in labels]

        series = chart_spec.get("series")
        if not isinstance(series, list) or not series:
            raise self._render_failed("chartSpec.series must be a non-empty list")

        normalized_series: list[dict[str, Any]] = []
        for index, item in enumerate(series):
            if not isinstance(item, dict):
                raise self._render_failed(f"chartSpec.series[{index}] must be an object")
            name = str(item.get("name") or f"Series {index + 1}")
            values = item.get("values")
            if not isinstance(values, list) or len(values) != len(normalized_labels):
                raise self._render_failed("chartSpec series values must match labels length")
            normalized_values = [self._numeric_value(value) for value in values]
            normalized_series.append({"name": name, "values": normalized_values})

        return {
            "type": chart_type,
            "unit": str(chart_spec.get("unit") or ""),
            "labels": normalized_labels,
            "series": normalized_series,
        }

    def _effective_chart_type(
        self,
        spec: dict[str, Any],
        template_context: TemplateContext | None,
    ) -> tuple[str, str]:
        profile = template_context.chart_profile_for("performance_chart") if template_context else None
        if profile is None:
            return spec["type"], "chart_spec"
        if profile.templateImageHasChart and profile.detectedChartType:
            return profile.detectedChartType, "template_image_analysis"
        return profile.fallbackChartType, "template_contract"

    def _numeric_value(self, value: Any) -> float:
        if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
            raise self._render_failed("chartSpec values must be finite numbers")
        return float(value)

    def _replace_placeholder(self, html: str, component_id: str, svg: str) -> str:
        matches = self._placeholder_matches(html, component_id)
        if len(matches) != 1:
            raise self._render_failed("Expected exactly one chart placeholder")

        start, end = matches[0]
        return self._remove_placeholder_css(html[:start] + svg + html[end:])

    def _placeholder_matches(self, html: str, component_id: str) -> list[tuple[int, int]]:
        marker = re.escape(component_id)
        attr = rf"\bdata-chart-placeholder\s*=\s*(?:\"{marker}\"|'{marker}')"
        paired = re.compile(
            rf"<(?P<tag>[A-Za-z][\w:-]*)\b(?=[^>]*{attr})[^>]*>.*?</(?P=tag)>",
            re.IGNORECASE | re.DOTALL,
        )
        self_closing = re.compile(
            rf"<[A-Za-z][\w:-]*\b(?=[^>]*{attr})[^>]*/\s*>",
            re.IGNORECASE | re.DOTALL,
        )
        matches = [(match.start(), match.end()) for match in paired.finditer(html)]
        matches.extend((match.start(), match.end()) for match in self_closing.finditer(html))
        return sorted(matches)

    def _render_bar_svg(self, spec: dict[str, Any], colors: list[str]) -> str:
        labels: list[str] = spec["labels"]
        series: list[dict[str, Any]] = spec["series"]
        unit: str = spec["unit"]
        values = [value for item in series for value in item["values"]]
        min_value = min(0.0, min(values))
        max_value = max(0.0, max(values))
        if min_value == max_value:
            min_value -= 1.0
            max_value += 1.0

        width = 760
        height = 360
        left = 64
        right = 24
        top = 34
        bottom = 74
        plot_width = width - left - right
        plot_height = height - top - bottom
        group_width = plot_width / len(labels)
        bar_width = max(4.0, min(28.0, (group_width - 20.0) / len(series) - 4.0))
        zero_y = self._scale_y(0.0, min_value, max_value, top, plot_height)
        parts = [
            '<svg data-chart-rendered="performance_chart" '
            'data-chart-type="bar" '
            f'viewBox="0 0 {width} {height}" role="img" aria-label="ETF performance chart">',
            "<title>ETF performance chart</title>",
            f"<desc>Bar chart comparing "
            f"{' and '.join(escape(item['name']) for item in series)} by period.</desc>",
            f'<rect x="0" y="0" width="{width}" height="{height}" rx="8" fill="#ffffff"/>',
        ]

        for ratio in (0.0, 0.25, 0.5, 0.75, 1.0):
            value = min_value + (max_value - min_value) * ratio
            y = self._scale_y(value, min_value, max_value, top, plot_height)
            parts.append(
                f'<line x1="{left}" y1="{y:.2f}" x2="{width - right}" y2="{y:.2f}" '
                'stroke="#e6eaf2" stroke-width="1"/>'
            )
            parts.append(
                f'<text x="{left - 8}" y="{y + 4:.2f}" text-anchor="end" '
                f'font-size="11" fill="#596273">{escape(self._format_value(value, unit))}</text>'
            )

        parts.append(
            f'<line x1="{left}" y1="{zero_y:.2f}" x2="{width - right}" y2="{zero_y:.2f}" '
            'stroke="#8d96a8" stroke-width="1.2"/>'
        )
        parts.append(
            f'<line x1="{left}" y1="{top}" x2="{left}" y2="{top + plot_height}" '
            'stroke="#8d96a8" stroke-width="1"/>'
        )

        for label_index, label in enumerate(labels):
            group_left = left + label_index * group_width
            group_center = group_left + group_width / 2
            bars_width = len(series) * bar_width + (len(series) - 1) * 4
            first_bar_x = group_center - bars_width / 2
            for series_index, item in enumerate(series):
                value = item["values"][label_index]
                value_y = self._scale_y(value, min_value, max_value, top, plot_height)
                bar_x = first_bar_x + series_index * (bar_width + 4)
                bar_y = min(value_y, zero_y)
                bar_height = max(1.0, abs(zero_y - value_y))
                color = colors[series_index % len(colors)]
                parts.append(
                    f'<rect x="{bar_x:.2f}" y="{bar_y:.2f}" width="{bar_width:.2f}" '
                    f'height="{bar_height:.2f}" fill="{color}" rx="2"/>'
                )
                label_y = bar_y - 5 if value >= 0 else bar_y + bar_height + 13
                parts.append(
                    f'<text x="{bar_x + bar_width / 2:.2f}" y="{label_y:.2f}" text-anchor="middle" '
                    f'font-size="10" fill="#263244">{escape(self._format_value(value, unit))}</text>'
                )
            parts.append(
                f'<text x="{group_center:.2f}" y="{height - 44}" text-anchor="middle" '
                f'font-size="12" fill="#263244">{escape(label)}</text>'
            )

        legend_x = left
        legend_y = height - 18
        for series_index, item in enumerate(series):
            color = colors[series_index % len(colors)]
            x = legend_x + series_index * 190
            parts.append(f'<rect x="{x}" y="{legend_y - 10}" width="12" height="12" fill="{color}" rx="2"/>')
            parts.append(
                f'<text x="{x + 18}" y="{legend_y}" font-size="12" fill="#263244">'
                f"{escape(item['name'])}</text>"
            )

        parts.append("</svg>")
        return "".join(parts)

    def _render_line_svg(self, spec: dict[str, Any], colors: list[str]) -> str:
        labels: list[str] = spec["labels"]
        series: list[dict[str, Any]] = spec["series"]
        unit: str = spec["unit"]
        values = [value for item in series for value in item["values"]]
        min_value = min(0.0, min(values))
        max_value = max(0.0, max(values))
        if min_value == max_value:
            min_value -= 1.0
            max_value += 1.0

        width = 760
        height = 360
        left = 64
        right = 24
        top = 34
        bottom = 74
        plot_width = width - left - right
        plot_height = height - top - bottom
        step = plot_width / max(1, len(labels) - 1)
        parts = [
            '<svg data-chart-rendered="performance_chart" '
            'data-chart-type="line" '
            f'viewBox="0 0 {width} {height}" role="img" aria-label="ETF performance chart">',
            "<title>ETF performance chart</title>",
            f"<desc>Line chart comparing "
            f"{' and '.join(escape(item['name']) for item in series)} by period.</desc>",
            f'<rect x="0" y="0" width="{width}" height="{height}" rx="8" fill="#ffffff"/>',
        ]

        for ratio in (0.0, 0.25, 0.5, 0.75, 1.0):
            value = min_value + (max_value - min_value) * ratio
            y = self._scale_y(value, min_value, max_value, top, plot_height)
            parts.append(
                f'<line x1="{left}" y1="{y:.2f}" x2="{width - right}" y2="{y:.2f}" '
                'stroke="#e6eaf2" stroke-width="1"/>'
            )
            parts.append(
                f'<text x="{left - 8}" y="{y + 4:.2f}" text-anchor="end" '
                f'font-size="11" fill="#596273">{escape(self._format_value(value, unit))}</text>'
            )

        zero_y = self._scale_y(0.0, min_value, max_value, top, plot_height)
        parts.append(
            f'<line x1="{left}" y1="{zero_y:.2f}" x2="{width - right}" y2="{zero_y:.2f}" '
            'stroke="#8d96a8" stroke-width="1.2"/>'
        )
        parts.append(
            f'<line x1="{left}" y1="{top}" x2="{left}" y2="{top + plot_height}" '
            'stroke="#8d96a8" stroke-width="1"/>'
        )

        for label_index, label in enumerate(labels):
            x = left + label_index * step
            parts.append(
                f'<text x="{x:.2f}" y="{height - 44}" text-anchor="middle" '
                f'font-size="12" fill="#263244">{escape(label)}</text>'
            )

        for series_index, item in enumerate(series):
            color = colors[series_index % len(colors)]
            points = [
                f"{left + value_index * step:.2f},"
                f"{self._scale_y(value, min_value, max_value, top, plot_height):.2f}"
                for value_index, value in enumerate(item["values"])
            ]
            parts.append(
                f'<polyline points="{" ".join(points)}" fill="none" stroke="{color}" '
                'stroke-width="3" stroke-linecap="round" stroke-linejoin="round"/>'
            )
            for value_index, value in enumerate(item["values"]):
                x = left + value_index * step
                y = self._scale_y(value, min_value, max_value, top, plot_height)
                parts.append(f'<circle cx="{x:.2f}" cy="{y:.2f}" r="4" fill="{color}"/>')
                parts.append(
                    f'<text x="{x:.2f}" y="{y - 9:.2f}" text-anchor="middle" '
                    f'font-size="10" fill="#263244">{escape(self._format_value(value, unit))}</text>'
                )

        legend_x = left
        legend_y = height - 18
        for series_index, item in enumerate(series):
            color = colors[series_index % len(colors)]
            x = legend_x + series_index * 190
            parts.append(f'<line x1="{x}" y1="{legend_y - 4}" x2="{x + 14}" y2="{legend_y - 4}" stroke="{color}" stroke-width="3"/>')
            parts.append(f'<circle cx="{x + 7}" cy="{legend_y - 4}" r="4" fill="{color}"/>')
            parts.append(
                f'<text x="{x + 20}" y="{legend_y}" font-size="12" fill="#263244">'
                f"{escape(item['name'])}</text>"
            )

        parts.append("</svg>")
        return "".join(parts)

    @staticmethod
    def _remove_placeholder_css(html: str) -> str:
        return re.sub(
            r"\s*[^{}]*\[[^\]]*data-chart-placeholder[^\]]*\][^{]*\{[^}]*\}",
            "",
            html,
            flags=re.IGNORECASE | re.DOTALL,
        )

    @staticmethod
    def _scale_y(value: float, min_value: float, max_value: float, top: int, plot_height: int) -> float:
        return top + (max_value - value) / (max_value - min_value) * plot_height

    @staticmethod
    def _format_value(value: float, unit: str) -> str:
        if abs(value - round(value)) < 0.05:
            formatted = str(int(round(value)))
        else:
            formatted = f"{value:.1f}"
        return f"{formatted}{unit}"

    @staticmethod
    def _render_failed(detail: str) -> ReportEngineError:
        return ReportEngineError(ErrorCode.RENDER_FAILED, detail, stage="stage4")


_NEUTRAL_CHART_COLORS = ["#4b5563", "#9ca3af", "#6b7280", "#d1d5db"]
_CSS_VARIABLE_PATTERN = re.compile(
    r"(?P<name>--chart-series-[1-4])\s*:\s*(?P<value>#[0-9a-fA-F]{3}(?:[0-9a-fA-F]{3})?)\b"
)


def _chart_series_colors(html: str) -> list[str]:
    values: dict[str, str] = {}
    for match in _CSS_VARIABLE_PATTERN.finditer(html):
        values[match.group("name")] = match.group("value").lower()

    colors = [
        values[name]
        for name in ("--chart-series-1", "--chart-series-2", "--chart-series-3", "--chart-series-4")
        if name in values
    ]
    return colors or _NEUTRAL_CHART_COLORS
