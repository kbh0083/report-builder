import unittest


class ChartRendererTests(unittest.TestCase):
    def test_render_and_inject_replaces_placeholder_with_inline_svg(self):
        from report_engine.chart_renderer import ChartRenderer

        component = _chart_component(chart_spec=_valid_chart_spec())
        html = _html_with_placeholder(component.componentId)

        rendered = ChartRenderer().render_and_inject(html, [component])

        self.assertIn('<svg data-chart-rendered="performance_chart"', rendered)
        self.assertIn("<title>ETF performance chart</title>", rendered)
        self.assertIn("Kodex 미국 S&amp;P500", rendered)
        self.assertIn("BM", rendered)
        self.assertIn("1개월", rendered)
        self.assertIn("%", rendered)
        self.assertNotIn("data-chart-placeholder", rendered)
        self.assertNotIn("<script", rendered.lower())
        self.assertNotIn("<canvas", rendered.lower())
        self.assertNotIn("chart.js", rendered.lower())
        self.assertNotIn("http://", rendered.lower())
        self.assertNotIn("https://", rendered.lower())

    def test_render_and_inject_supports_line_chart_spec_from_novita(self):
        from report_engine.chart_renderer import ChartRenderer

        component = _chart_component(
            chart_spec={
                "type": "line",
                "title": "ETF 성과 추이",
                "unit": "%",
                "labels": ["1개월", "3개월", "6개월", "1년", "상장이후"],
                "series": [
                    {"name": "Kodex 미국나스닥100", "values": [6.5, 16.7, 3.9, 25.7, 113.7]},
                    {"name": "BM", "values": [6.2, 16.5, 3.7, 25.8, 116.6]},
                ],
            }
        )

        rendered = ChartRenderer().render_and_inject(_html_with_placeholder(component.componentId), [component])

        self.assertIn('<svg data-chart-rendered="performance_chart"', rendered)
        self.assertIn('data-chart-type="line"', rendered)
        self.assertIn("Kodex 미국나스닥100", rendered)
        self.assertIn("상장이후", rendered)
        self.assertIn("<polyline", rendered)
        self.assertNotIn("data-chart-placeholder", rendered)

    def test_render_and_inject_rejects_invalid_chart_specs(self):
        from report_engine.chart_renderer import ChartRenderer
        from report_engine.errors import ErrorCode, ReportEngineError

        cases = [
            ("missing_spec", None),
            ("missing_labels", {"type": "bar", "series": [{"name": "ETF", "values": [1.0]}]}),
            ("empty_series", {"type": "bar", "labels": ["1개월"], "series": []}),
            (
                "values_length_mismatch",
                {"type": "bar", "labels": ["1개월", "3개월"], "series": [{"name": "ETF", "values": [1.0]}]},
            ),
            (
                "unsupported_type",
                {"type": "pie", "labels": ["1개월"], "series": [{"name": "ETF", "values": [1.0]}]},
            ),
        ]

        for name, chart_spec in cases:
            with self.subTest(name=name):
                component = _chart_component(chart_spec=chart_spec)
                with self.assertRaises(ReportEngineError) as caught:
                    ChartRenderer().render_and_inject(_html_with_placeholder(component.componentId), [component])

                self.assertEqual(caught.exception.code, ErrorCode.RENDER_FAILED)
                self.assertEqual(caught.exception.stage, "stage4")

    def test_render_and_inject_rejects_missing_or_duplicate_placeholder(self):
        from report_engine.chart_renderer import ChartRenderer
        from report_engine.errors import ErrorCode, ReportEngineError

        component = _chart_component(chart_spec=_valid_chart_spec())
        cases = [
            ("missing", "<!doctype html><html><body><section></section></body></html>"),
            (
                "duplicate",
                _html_with_placeholder(component.componentId)
                + _html_with_placeholder(component.componentId),
            ),
        ]

        for name, html in cases:
            with self.subTest(name=name):
                with self.assertRaises(ReportEngineError) as caught:
                    ChartRenderer().render_and_inject(html, [component])

                self.assertEqual(caught.exception.code, ErrorCode.RENDER_FAILED)
                self.assertEqual(caught.exception.stage, "stage4")

    def test_render_and_inject_requires_exactly_one_performance_chart_component(self):
        from report_engine.chart_renderer import ChartRenderer
        from report_engine.errors import ErrorCode, ReportEngineError

        component = _chart_component(chart_spec=_valid_chart_spec())
        html = _html_with_placeholder(component.componentId)

        for components in ([], [component, component]):
            with self.subTest(count=len(components)):
                with self.assertRaises(ReportEngineError) as caught:
                    ChartRenderer().render_and_inject(html, components)

                self.assertEqual(caught.exception.code, ErrorCode.RENDER_FAILED)
                self.assertEqual(caught.exception.stage, "stage4")


def _valid_chart_spec():
    return {
        "type": "bar",
        "unit": "%",
        "labels": ["1개월", "3개월", "6개월"],
        "series": [
            {"name": "Kodex 미국 S&P500", "values": [1.4, 8.9, -1.4]},
            {"name": "BM", "values": [1.6, 9.2, -1.8]},
        ],
    }


def _chart_component(chart_spec):
    from report_engine.models import Stage2Component

    return Stage2Component(
        componentId="comp_chart",
        dataSourceId="source_chart",
        datasetId="data_test",
        monthId="2026-03",
        componentKey="performance_chart",
        renderType="chart",
        html='<section data-component-id="comp_chart"><canvas></canvas></section>',
        chartSpec=chart_spec,
        styled=False,
    )


def _html_with_placeholder(component_id):
    return (
        "<!doctype html><html><body>"
        f'<section data-component-id="{component_id}">'
        f'<div class="chart-slot" data-chart-placeholder="{component_id}"></div>'
        "</section></body></html>"
    )


if __name__ == "__main__":
    unittest.main()
