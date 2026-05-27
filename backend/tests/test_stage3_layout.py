import json
import unittest
from pathlib import Path


BACKEND_ROOT = Path(__file__).resolve().parents[1]
WORKSPACE_ROOT = BACKEND_ROOT.parent


class Stage3LayoutTests(unittest.TestCase):
    def setUp(self):
        from report_engine.repository import ReportRepository
        from report_engine.stage1_template import Stage1TemplateService

        self.repository = ReportRepository(WORKSPACE_ROOT)
        self.template = Stage1TemplateService(self.repository).load_template_context("tpl_kb_monthly_guidebook")
        self.dataset = self.repository.load_dataset("data_kodex_us_sp500")
        self.month_snapshot = self.repository.load_month_snapshot("data_kodex_us_sp500", "2026-03")
        self.components = self.repository.load_sample_components("data_kodex_us_sp500", "2026-03")

    def test_fake_adapter_generates_single_html_with_all_component_ids(self):
        from report_engine.stage3_layout import Stage3LayoutService

        adapter = FakeLayoutAdapter()
        service = Stage3LayoutService(adapter)

        prompt_input = service.build_prompt_input(self.template, self.dataset, self.month_snapshot, self.components)
        html = service.generate_report_draft(prompt_input, self.components)

        self.assertTrue(html.lower().startswith("<!doctype html>"))
        for component in self.components:
            self.assertIn(component.componentId, html)
        self.assertEqual(adapter.last_prompt_input, prompt_input)
        self.assertIn("previewImage", prompt_input["template"])
        self.assertIn("sourceHtml", prompt_input["template"])
        self.assertEqual(prompt_input["dataset"]["datasetId"], "data_kodex_us_sp500")
        self.assertEqual(prompt_input["monthSnapshot"]["monthId"], "2026-03")
        self.assertIn("data-chart-placeholder", json.dumps(prompt_input, ensure_ascii=False))
        self.assertNotIn("chartSpec", json.dumps(prompt_input, ensure_ascii=False))
        self.assertNotIn("<canvas", json.dumps(prompt_input, ensure_ascii=False).lower())
        self.assertIn("Footer must stay in normal document flow.", prompt_input["constraints"])
        self.assertIn("Do not use position:absolute or position:fixed for footer or bottom disclaimers.", prompt_input["constraints"])
        self.assertNotIn("LLM_API_KEY", json.dumps(prompt_input, ensure_ascii=False))
        self.assertNotIn("apiKey", json.dumps(prompt_input, ensure_ascii=False))

    def test_rejects_layout_that_renders_chart_before_stage4(self):
        from report_engine.errors import ErrorCode, ReportEngineError
        from report_engine.stage3_layout import Stage3LayoutService

        service = Stage3LayoutService(ChartRenderingAdapter())
        prompt_input = service.build_prompt_input(self.template, self.dataset, self.month_snapshot, self.components)

        with self.assertRaises(ReportEngineError) as caught:
            service.generate_report_draft(prompt_input, self.components)

        self.assertEqual(caught.exception.code, ErrorCode.LAYOUT_GENERATION_INVALID)

    def test_rejects_layout_with_absolute_footer_overlap_risk(self):
        from report_engine.errors import ErrorCode, ReportEngineError
        from report_engine.stage3_layout import Stage3LayoutService

        service = Stage3LayoutService(AbsoluteFooterAdapter())
        prompt_input = service.build_prompt_input(self.template, self.dataset, self.month_snapshot, self.components)

        with self.assertRaises(ReportEngineError) as caught:
            service.generate_report_draft(prompt_input, self.components)

        self.assertEqual(caught.exception.code, ErrorCode.LAYOUT_GENERATION_INVALID)

    def test_rejects_layout_missing_component_id(self):
        from report_engine.errors import ErrorCode, ReportEngineError
        from report_engine.stage3_layout import Stage3LayoutService

        service = Stage3LayoutService(MissingComponentAdapter())
        prompt_input = service.build_prompt_input(self.template, self.dataset, self.month_snapshot, self.components)

        with self.assertRaises(ReportEngineError) as caught:
            service.generate_report_draft(prompt_input, self.components)

        self.assertEqual(caught.exception.code, ErrorCode.LAYOUT_GENERATION_INVALID)

    def test_accepts_markdown_fenced_html_from_llm(self):
        from report_engine.stage3_layout import Stage3LayoutService

        service = Stage3LayoutService(FencedHtmlAdapter())
        prompt_input = service.build_prompt_input(self.template, self.dataset, self.month_snapshot, self.components)

        html = service.generate_report_draft(prompt_input, self.components)

        self.assertTrue(html.lower().startswith("<!doctype html>"))
        self.assertNotIn("```", html)
        for component in self.components:
            self.assertIn(component.componentId, html)


class FakeLayoutAdapter:
    def generate_stage3_layout(self, prompt_input):
        self.last_prompt_input = prompt_input
        body = "\n".join(item["html"] for item in prompt_input["components"])
        return f"<!doctype html><html><body>{body}</body></html>"


class MissingComponentAdapter:
    def generate_stage3_layout(self, prompt_input):
        body = "\n".join(
            f'<section data-component-id="{item["componentId"]}"></section>'
            for item in prompt_input["components"][:-1]
        )
        return f"<!doctype html><html><body>{body}</body></html>"


class FencedHtmlAdapter:
    def generate_stage3_layout(self, prompt_input):
        body = "\n".join(item["html"] for item in prompt_input["components"])
        return f"```html\n<!doctype html><html><body>{body}</body></html>\n```"


class ChartRenderingAdapter:
    def generate_stage3_layout(self, prompt_input):
        body = "\n".join(
            f'<section data-component-id="{component_id}"><svg><rect width="1" height="1"></rect></svg></section>'
            if item["renderType"] == "chart"
            else item["html"]
            for item in prompt_input["components"]
            for component_id in [item["componentId"]]
        )
        return f"<!doctype html><html><body>{body}</body></html>"


class AbsoluteFooterAdapter:
    def generate_stage3_layout(self, prompt_input):
        body = "\n".join(item["html"] for item in prompt_input["components"])
        return (
            "<!doctype html><html><head><style>"
            "footer { position: absolute; bottom: 20mm; left: 20mm; right: 20mm; }"
            "</style></head><body>"
            f"{body}<footer>disclaimer</footer>"
            "</body></html>"
        )


if __name__ == "__main__":
    unittest.main()
