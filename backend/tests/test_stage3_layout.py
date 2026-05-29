import json
import tempfile
import unittest
from pathlib import Path


BACKEND_ROOT = Path(__file__).resolve().parents[1]
WORKSPACE_ROOT = BACKEND_ROOT.parent

_TEMPLATE_CSS_VARS = (
    ":root { --report-primary: #b61f2b; --report-accent: #f3e8e8; "
    "--chart-series-1: #b61f2b; --chart-series-2: #777777; }"
)


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
        from report_engine.prompt_store import PromptStore
        from report_engine.stage3_layout import Stage3LayoutService

        adapter = FakeLayoutAdapter()
        with tempfile.TemporaryDirectory() as tmpdir:
            prompt_root = Path(tmpdir)
            _write_prompt_json(
                prompt_root,
                "03_layout_visual_objective.json",
                [
                    "Custom visual objective: template preview image.",
                    "Custom visual objective: visual reference only.",
                ],
            )
            _write_prompt_json(
                prompt_root,
                "03_layout_constraints.json",
                [
                    "Custom constraint: Generate document-local CSS in a non-empty <style> block.",
                    "Custom constraint: Footer must stay in normal document flow.",
                    "Custom constraint: Do not use position:absolute or position:fixed for footer or bottom disclaimers.",
                    "Custom constraint: Do not copy data labels, table values, or prose from template preview image.",
                    "Custom constraint: Match the template preview image as closely as possible.",
                ],
            )
            _write_prompt_json(prompt_root, "03_layout_correction_requirements.json", ["Return one complete HTML document."])
            service = Stage3LayoutService(adapter, prompt_store=PromptStore(prompt_root))

            prompt_input = service.build_prompt_input(self.template, self.dataset, self.month_snapshot, self.components)
            html = service.generate_report_draft(prompt_input, self.components)

        self.assertTrue(html.lower().startswith("<!doctype html>"))
        for component in self.components:
            self.assertIn(component.componentId, html)
        self.assertEqual(adapter.last_prompt_input, prompt_input)
        self.assertIn("previewImage", prompt_input["template"])
        self.assertNotIn("sourceHtml", prompt_input["template"])
        self.assertEqual(prompt_input["dataset"]["datasetId"], "data_kodex_us_sp500")
        self.assertNotIn("styleCandidates", prompt_input["dataset"])
        self.assertEqual(
            prompt_input["visualObjective"],
            [
                "Custom visual objective: template preview image.",
                "Custom visual objective: visual reference only.",
            ],
        )
        self.assertEqual(prompt_input["monthSnapshot"]["monthId"], "2026-03")
        self.assertIn("data-chart-placeholder", json.dumps(prompt_input, ensure_ascii=False))
        self.assertNotIn("chartSpec", json.dumps(prompt_input, ensure_ascii=False))
        self.assertNotIn("<canvas", json.dumps(prompt_input, ensure_ascii=False).lower())
        self.assertIn("Custom constraint: Footer must stay in normal document flow.", prompt_input["constraints"])
        self.assertIn("Custom constraint: Do not use position:absolute or position:fixed for footer or bottom disclaimers.", prompt_input["constraints"])
        self.assertIn("Custom constraint: Generate document-local CSS in a non-empty <style> block.", prompt_input["constraints"])
        self.assertIn("Custom constraint: Match the template preview image as closely as possible.", prompt_input["constraints"])
        self.assertIn("Custom constraint: Do not copy data labels, table values, or prose from template preview image.", prompt_input["constraints"])
        self.assertNotIn("LLM_API_KEY", json.dumps(prompt_input, ensure_ascii=False))
        self.assertNotIn("apiKey", json.dumps(prompt_input, ensure_ascii=False))

    def test_retries_once_when_template_derived_css_variables_are_missing(self):
        from report_engine.stage3_layout import Stage3LayoutService

        adapter = CssVariablesMissingThenValidAdapter()
        service = Stage3LayoutService(adapter)
        prompt_input = service.build_prompt_input(self.template, self.dataset, self.month_snapshot, self.components)

        html = service.generate_report_draft(prompt_input, self.components)

        self.assertIn("--report-primary: #b61f2b", html)
        self.assertEqual(adapter.call_count, 2)
        requirements = "\n".join(adapter.prompt_inputs[1]["correction"]["requirements"])
        self.assertIn("--report-primary", requirements)
        self.assertIn("--chart-series-1", requirements)
        self.assertIn("template preview image", requirements)

    def test_retries_once_when_initial_layout_invalid_then_accepts_correction(self):
        from report_engine.prompt_store import PromptStore
        from report_engine.stage3_layout import Stage3LayoutService

        adapter = CssMissingThenValidAdapter()
        with tempfile.TemporaryDirectory() as tmpdir:
            prompt_root = Path(tmpdir)
            _write_default_stage3_prompt_files(prompt_root)
            _write_prompt_json(prompt_root, "03_layout_correction_requirements.json", ["Custom correction: Return one complete HTML document."])
            service = Stage3LayoutService(adapter, prompt_store=PromptStore(prompt_root))
            prompt_input = service.build_prompt_input(self.template, self.dataset, self.month_snapshot, self.components)

            html = service.generate_report_draft(prompt_input, self.components, template_image_data_url="data:image/png;base64,abc")

        self.assertIn("<!doctype html>", html)
        self.assertEqual(adapter.call_count, 2)
        self.assertEqual(adapter.template_image_data_urls, ["data:image/png;base64,abc", "data:image/png;base64,abc"])
        correction = adapter.prompt_inputs[1]["correction"]
        self.assertEqual(correction["attempt"], 1)
        self.assertIn("LAYOUT_GENERATION_INVALID", correction["previousError"])
        self.assertIn("rejectedHtml", correction)
        self.assertIn("Custom correction: Return one complete HTML document.", correction["requirements"])

    def test_default_stage3_correction_prioritizes_stage2_component_preservation(self):
        from report_engine.prompt_store import PromptStore

        requirements = " ".join(PromptStore().read_json("03_layout_correction_requirements.json")).lower()

        self.assertIn("stage 2 component preservation takes priority", requirements)
        self.assertIn("layout and style reference", requirements)
        self.assertIn("do not add template sample sections", requirements)
        self.assertIn("do not remove supplied stage 2 components", requirements)
        self.assertIn("verificationcorrection.revisioncontract", requirements)
        self.assertIn("minimal_patch", requirements)
        self.assertIn("basereportdrafthtml", requirements)
        self.assertIn("revisionprofile.forbiddencsstokens", requirements)
        self.assertIn("do not rewrite the entire document", requirements)
        self.assertIn("do not normalize", requirements)
        self.assertIn("correction.strictliteralpreservation", requirements)

    def test_validator_accepts_stage2_content_without_template_sample_section_labels(self):
        from report_engine.stage3_layout import Stage3LayoutService, stage3_component_html

        body = "\n".join(stage3_component_html(component) for component in self.components)
        html = (
            "<!doctype html><html><head><style>"
            f"{_TEMPLATE_CSS_VARS} body {{ margin: 0; }}"
            "</style></head><body>"
            f"{body}"
            "</body></html>"
        )

        Stage3LayoutService(FakeLayoutAdapter()).validate_report_draft(html, self.components)

        self.assertNotIn("ETF 개요", html)
        self.assertNotIn("ETF 자산 현황", html)
        self.assertNotIn("분배금 지급 현황", html)

    def test_invalid_stage3_prompt_json_raises_config_invalid(self):
        from report_engine.errors import ErrorCode, ReportEngineError
        from report_engine.prompt_store import PromptStore
        from report_engine.stage3_layout import Stage3LayoutService

        with tempfile.TemporaryDirectory() as tmpdir:
            prompt_root = Path(tmpdir)
            _write_prompt_file(prompt_root, "03_layout_visual_objective.json", "{not-json")
            _write_prompt_json(prompt_root, "03_layout_constraints.json", [])
            _write_prompt_json(prompt_root, "03_layout_correction_requirements.json", [])
            service = Stage3LayoutService(FakeLayoutAdapter(), prompt_store=PromptStore(prompt_root))

            with self.assertRaises(ReportEngineError) as caught:
                service.build_prompt_input(self.template, self.dataset, self.month_snapshot, self.components)

        self.assertEqual(caught.exception.code, ErrorCode.CONFIG_INVALID)
        self.assertIn("03_layout_visual_objective.json", str(caught.exception))

    def test_empty_stage3_prompt_json_list_raises_config_invalid(self):
        from report_engine.errors import ErrorCode, ReportEngineError
        from report_engine.prompt_store import PromptStore
        from report_engine.stage3_layout import Stage3LayoutService

        with tempfile.TemporaryDirectory() as tmpdir:
            prompt_root = Path(tmpdir)
            _write_prompt_json(prompt_root, "03_layout_visual_objective.json", [])
            _write_prompt_json(prompt_root, "03_layout_constraints.json", ["Return one complete HTML document."])
            _write_prompt_json(prompt_root, "03_layout_correction_requirements.json", ["Return one complete HTML document."])
            service = Stage3LayoutService(FakeLayoutAdapter(), prompt_store=PromptStore(prompt_root))

            with self.assertRaises(ReportEngineError) as caught:
                service.build_prompt_input(self.template, self.dataset, self.month_snapshot, self.components)

        self.assertEqual(caught.exception.code, ErrorCode.CONFIG_INVALID)
        self.assertIn("non-empty list of strings", str(caught.exception))

    def test_retries_once_when_source_text_is_missing_then_accepts_correction(self):
        from report_engine.stage3_layout import Stage3LayoutService

        adapter = SourceMissingThenValidAdapter()
        service = Stage3LayoutService(adapter)
        prompt_input = service.build_prompt_input(self.template, self.dataset, self.month_snapshot, self.components)

        html = service.generate_report_draft(prompt_input, self.components)

        self.assertIn("NVIDIA Corp", html)
        self.assertEqual(adapter.call_count, 2)
        self.assertIn("source fragments", " ".join(adapter.prompt_inputs[1]["correction"]["requirements"]))

    def test_footer_flow_correction_prompt_names_forbidden_positioning(self):
        from report_engine.stage3_layout import Stage3LayoutService

        adapter = FooterAbsoluteThenValidAdapter()
        service = Stage3LayoutService(adapter)
        prompt_input = service.build_prompt_input(self.template, self.dataset, self.month_snapshot, self.components)

        html = service.generate_report_draft(prompt_input, self.components)

        correction = adapter.prompt_inputs[1]["correction"]
        requirements = "\n".join(correction["requirements"])
        self.assertIn("<footer>normal flow disclaimer</footer>", html)
        self.assertIn("Remove position:absolute and position:fixed from footer", requirements)
        self.assertIn("Do not anchor footer or bottom disclaimers with bottom/left/right overlay coordinates.", requirements)
        self.assertIn("Rewrite forbidden footer CSS from rejectedHtml instead of copying it.", requirements)

    def test_correction_prompt_lists_exact_missing_numeric_fragments(self):
        from report_engine.models import Stage2Component
        from report_engine.stage3_layout import Stage3LayoutService

        component = Stage2Component(
            componentId="comp_summary",
            dataSourceId="ds_summary",
            datasetId="data_x",
            monthId="2026-03",
            componentKey="performance_summary",
            renderType="table",
            html=(
                '<section data-component-id="comp_summary">'
                "<table><tbody><tr>"
                "<td>-4.89%</td><td>6.65%</td><td>9.55%</td>"
                "</tr></tbody></table>"
                "</section>"
            ),
            chartSpec=None,
            styled=False,
        )
        adapter = PercentMissingThenStructuredCorrectionAdapter()

        html = Stage3LayoutService(adapter).generate_report_draft(
            {"components": [{"componentId": component.componentId, "html": component.html}]},
            [component],
        )

        correction = adapter.prompt_inputs[1]["correction"]
        self.assertIn("<td>-4.89%</td>", html)
        self.assertEqual(
            correction["sourceFragmentViolations"],
            [
                {
                    "componentId": "comp_summary",
                    "componentKey": "performance_summary",
                    "missingFragments": ["-4.89%", "6.65%", "9.55%"],
                }
            ],
        )
        self.assertIn(
            "Do not remove sign prefixes, percent symbols, currency or unit symbols, commas, or decimal points.",
            correction["requirements"],
        )

    def test_retries_three_corrections_until_source_fragments_are_preserved(self):
        from report_engine.models import Stage2Component
        from report_engine.stage3_layout import Stage3LayoutService

        component = _woori_live_failure_component()
        adapter = WooriFragmentsValidOnFourthCallAdapter()
        recorded_attempts = []

        html = Stage3LayoutService(adapter).generate_report_draft(
            {"components": [{"componentId": component.componentId, "componentKey": component.componentKey, "html": component.html}]},
            [component],
            max_correction_attempts=3,
            attempt_recorder=recorded_attempts.append,
        )

        self.assertIn("-4.89%", html)
        self.assertIn("자료 : 삼성자산운용, 2026.03.31 기준", html)
        self.assertEqual(adapter.call_count, 4)
        self.assertEqual([item.get("correction", {}).get("attempt") for item in adapter.prompt_inputs[1:]], [1, 2, 3])
        third_correction = adapter.prompt_inputs[3]["correction"]
        self.assertTrue(third_correction["strictLiteralPreservation"])
        self.assertEqual(
            third_correction["mustRenderFragments"],
            [
                "-4.89%",
                "6.65%",
                "9.55%",
                "자료 : 삼성자산운용, 2026.03.31 기준",
            ],
        )
        self.assertEqual([attempt["attempt"] for attempt in recorded_attempts], [0, 1, 2, 3])
        self.assertEqual(recorded_attempts[-1]["status"], "passed")

    def test_rejects_when_correction_output_remains_invalid(self):
        from report_engine.errors import ErrorCode, ReportEngineError
        from report_engine.stage3_layout import Stage3LayoutService

        adapter = AlwaysCssMissingAdapter()
        service = Stage3LayoutService(adapter)
        prompt_input = service.build_prompt_input(self.template, self.dataset, self.month_snapshot, self.components)

        with self.assertRaises(ReportEngineError) as caught:
            service.generate_report_draft(prompt_input, self.components)

        self.assertEqual(caught.exception.code, ErrorCode.LAYOUT_GENERATION_INVALID)
        self.assertEqual(adapter.call_count, 4)
        loop = getattr(caught.exception, "stage3_validation_loop")
        self.assertEqual(loop["maxCorrectionAttempts"], 3)
        self.assertEqual([attempt["attempt"] for attempt in loop["attempts"]], [0, 1, 2, 3])
        self.assertEqual(loop["attempts"][-1]["status"], "failed")

    def test_rejects_layout_missing_non_chart_source_fragment(self):
        from report_engine.errors import ErrorCode, ReportEngineError
        from report_engine.stage3_layout import Stage3LayoutService

        service = Stage3LayoutService(SourceMissingAdapter())
        prompt_input = service.build_prompt_input(self.template, self.dataset, self.month_snapshot, self.components)
        html = service._normalize_html(service.llm_adapter.generate_stage3_layout(prompt_input))

        with self.assertRaises(ReportEngineError) as caught:
            service.validate_report_draft(html, self.components)

        self.assertEqual(caught.exception.code, ErrorCode.LAYOUT_GENERATION_INVALID)
        self.assertIn("source fragments", str(caught.exception))

    def test_repairs_source_fragment_violations_after_corrections_are_exhausted(self):
        from report_engine.stage3_layout import Stage3LayoutService

        component = _kb_repair_component()
        adapter = KbFragmentsAlwaysInvalidAdapter()
        recorded_attempts = []
        prompt_input = {
            "components": [
                {
                    "componentId": component.componentId,
                    "componentKey": component.componentKey,
                    "renderType": component.renderType,
                    "html": component.html,
                }
            ]
        }

        html = Stage3LayoutService(adapter).generate_report_draft(
            prompt_input,
            [component],
            max_correction_attempts=1,
            attempt_recorder=recorded_attempts.append,
        )

        self.assertEqual(adapter.call_count, 2)
        self.assertIn("6개월", html)
        self.assertIn("1년", html)
        self.assertIn("연초후", html)
        self.assertIn("0.56%", html)
        self.assertIn("19.09%", html)
        self.assertIn("No.", html)
        self.assertIn("보유비중(%)", html)
        self.assertIn("합계", html)
        self.assertIn("37.37", html)
        self.assertEqual([attempt["phase"] for attempt in recorded_attempts], ["initial", "correction", "local_repair"])
        self.assertEqual([attempt["status"] for attempt in recorded_attempts], ["failed", "failed", "passed"])
        self.assertEqual(
            recorded_attempts[-1]["localRepair"]["repairedComponents"][0]["componentId"],
            component.componentId,
        )

    def test_allows_template_heading_relabel_when_source_body_fragments_are_preserved(self):
        from report_engine.stage3_layout import Stage3LayoutService

        component = _preservation_component()
        service = Stage3LayoutService(HeadingRelabeledAdapter())
        prompt_input = {
            "components": [
                {
                    "componentId": component.componentId,
                    "componentKey": component.componentKey,
                    "renderType": component.renderType,
                    "html": component.html,
                }
            ]
        }

        html = service.generate_report_draft(prompt_input, [component])

        self.assertIn("ETF 성과 추이", html)
        self.assertNotIn("ETF 성과 추이 요약", html)

    def test_rejects_layout_missing_source_table_header(self):
        from report_engine.errors import ErrorCode, ReportEngineError
        from report_engine.stage3_layout import Stage3LayoutService

        component = _preservation_component()
        service = Stage3LayoutService(MissingTableHeaderAdapter())
        prompt_input = {"components": [{"componentId": component.componentId, "html": component.html}]}
        html = service._normalize_html(service.llm_adapter.generate_stage3_layout(prompt_input))

        with self.assertRaises(ReportEngineError) as caught:
            service.validate_report_draft(html, [component])

        self.assertEqual(caught.exception.code, ErrorCode.LAYOUT_GENERATION_INVALID)

    def test_rejects_layout_missing_source_table_number(self):
        from report_engine.errors import ErrorCode, ReportEngineError
        from report_engine.stage3_layout import Stage3LayoutService

        component = _preservation_component()
        service = Stage3LayoutService(MissingTableNumberAdapter())
        prompt_input = {"components": [{"componentId": component.componentId, "html": component.html}]}
        html = service._normalize_html(service.llm_adapter.generate_stage3_layout(prompt_input))

        with self.assertRaises(ReportEngineError) as caught:
            service.validate_report_draft(html, [component])

        self.assertEqual(caught.exception.code, ErrorCode.LAYOUT_GENERATION_INVALID)

    def test_rejects_layout_missing_source_list_item(self):
        from report_engine.errors import ErrorCode, ReportEngineError
        from report_engine.stage3_layout import Stage3LayoutService

        component = _preservation_component()
        service = Stage3LayoutService(MissingListItemAdapter())
        prompt_input = {"components": [{"componentId": component.componentId, "html": component.html}]}

        with self.assertRaises(ReportEngineError) as caught:
            service.generate_report_draft(prompt_input, [component])

        self.assertEqual(caught.exception.code, ErrorCode.LAYOUT_GENERATION_INVALID)

    def test_allows_decorative_list_markers_to_move_out_of_visible_text(self):
        from report_engine.models import Stage2Component
        from report_engine.stage3_layout import Stage3LayoutService

        component = Stage2Component(
            componentId="comp_outlook",
            dataSourceId="ds_outlook",
            datasetId="data_x",
            monthId="2026-03",
            componentKey="outlook",
            renderType="article",
            html=(
                '<section data-component-id="comp_outlook">'
                "<ul>"
                "<li>① NVIDIA와 BROADCOM을 중심으로 한 AI 반도체 수요가 지수 성과의 핵심 동력으로 작용할 전망</li>"
                "<li>② 대형 플랫폼 기업의 광고, 클라우드, 구독 매출 회복이 <strong>이익 안정성</strong>을 높일 가능성</li>"
                "<li>③ 높은 성장주 집중도는 금리 상승 또는 규제 이슈 발생 시 단기 조정 폭을 키울 수 있음</li>"
                "</ul>"
                "</section>"
            ),
            chartSpec=None,
            styled=False,
        )

        html = Stage3LayoutService(ListMarkerMovedAdapter()).generate_report_draft(
            {"components": [{"componentId": component.componentId, "html": component.html}]},
            [component],
        )

        self.assertIn('data-num="1"', html)
        self.assertIn("이익 안정성", html)

    def test_chart_component_source_text_is_not_required_in_stage3(self):
        from report_engine.models import Stage2Component
        from report_engine.stage3_layout import Stage3LayoutService

        chart = Stage2Component(
            componentId="comp_chart",
            dataSourceId="ds_chart",
            datasetId="data_x",
            monthId="2026-03",
            componentKey="performance_chart",
            renderType="chart",
            html='<section data-component-id="comp_chart"><h2>Chart Source Text</h2><canvas>chart-only-source</canvas></section>',
            chartSpec={"type": "line"},
            styled=False,
        )
        summary = Stage2Component(
            componentId="comp_summary",
            dataSourceId="ds_summary",
            datasetId="data_x",
            monthId="2026-03",
            componentKey="performance_summary",
            renderType="table",
            html='<section data-component-id="comp_summary"><p>Preserve this summary value 12.34</p></section>',
            chartSpec=None,
            styled=False,
        )
        service = Stage3LayoutService(ChartPlaceholderOnlyAdapter())
        prompt_input = {
            "components": [
                {"componentId": "comp_chart", "html": '<section data-component-id="comp_chart"><div data-chart-placeholder="comp_chart"></div></section>'},
                {"componentId": "comp_summary", "html": summary.html},
            ]
        }

        html = service.generate_report_draft(prompt_input, [chart, summary])

        self.assertIn('data-chart-placeholder="comp_chart"', html)
        self.assertNotIn("chart-only-source", html)
        self.assertIn("Preserve this summary value 12.34", html)

    def test_accepts_chart_placeholder_without_component_id_marker(self):
        from report_engine.models import Stage2Component
        from report_engine.stage3_layout import Stage3LayoutService

        chart = Stage2Component(
            componentId="comp_chart",
            dataSourceId="ds_chart",
            datasetId="data_x",
            monthId="2026-03",
            componentKey="performance_chart",
            renderType="chart",
            html='<section data-component-id="comp_chart"><div data-chart-placeholder="comp_chart"></div></section>',
            chartSpec={"type": "line"},
            styled=False,
        )
        summary = Stage2Component(
            componentId="comp_summary",
            dataSourceId="ds_summary",
            datasetId="data_x",
            monthId="2026-03",
            componentKey="performance_summary",
            renderType="table",
            html='<section data-component-id="comp_summary"><p>Preserve this summary value 12.34</p></section>',
            chartSpec=None,
            styled=False,
        )

        html = Stage3LayoutService(ChartPlaceholderWithoutComponentIdAdapter()).generate_report_draft(
            {"components": [{"componentId": "comp_chart"}, {"componentId": "comp_summary"}]},
            [chart, summary],
        )

        self.assertIn('data-chart-placeholder="comp_chart"', html)
        self.assertNotIn('data-component-id="comp_chart"', html)
        self.assertIn("Preserve this summary value 12.34", html)

    def test_accepts_chart_placeholder_when_css_uses_exact_attribute_selector(self):
        from report_engine.models import Stage2Component
        from report_engine.stage3_layout import Stage3LayoutService

        chart = Stage2Component(
            componentId="comp_chart",
            dataSourceId="ds_chart",
            datasetId="data_x",
            monthId="2026-03",
            componentKey="performance_chart",
            renderType="chart",
            html='<section data-component-id="comp_chart"><div data-chart-placeholder="comp_chart"></div></section>',
            chartSpec={"type": "line"},
            styled=False,
        )

        html = Stage3LayoutService(ChartPlaceholderWithExactCssSelectorAdapter()).generate_report_draft(
            {"components": [{"componentId": "comp_chart"}]},
            [chart],
        )

        self.assertIn('[data-chart-placeholder="comp_chart"]', html)
        self.assertIn('data-chart-placeholder="comp_chart"', html)

    def test_rejects_chart_component_without_placeholder(self):
        from report_engine.errors import ErrorCode, ReportEngineError
        from report_engine.models import Stage2Component
        from report_engine.stage3_layout import Stage3LayoutService

        chart = Stage2Component(
            componentId="comp_chart",
            dataSourceId="ds_chart",
            datasetId="data_x",
            monthId="2026-03",
            componentKey="performance_chart",
            renderType="chart",
            html='<section data-component-id="comp_chart"><div data-chart-placeholder="comp_chart"></div></section>',
            chartSpec={"type": "line"},
            styled=False,
        )

        with self.assertRaises(ReportEngineError) as caught:
            Stage3LayoutService(ChartComponentWithoutPlaceholderAdapter()).generate_report_draft(
                {"components": [{"componentId": "comp_chart"}]},
                [chart],
            )

        self.assertEqual(caught.exception.code, ErrorCode.LAYOUT_GENERATION_INVALID)
        self.assertIn("chart placeholders", str(caught.exception))

    def test_rejects_duplicate_chart_placeholders(self):
        from report_engine.errors import ErrorCode, ReportEngineError
        from report_engine.models import Stage2Component
        from report_engine.stage3_layout import Stage3LayoutService

        chart = Stage2Component(
            componentId="comp_chart",
            dataSourceId="ds_chart",
            datasetId="data_x",
            monthId="2026-03",
            componentKey="performance_chart",
            renderType="chart",
            html='<section data-component-id="comp_chart"><div data-chart-placeholder="comp_chart"></div></section>',
            chartSpec={"type": "line"},
            styled=False,
        )

        with self.assertRaises(ReportEngineError) as caught:
            Stage3LayoutService(DuplicateChartPlaceholderAdapter()).generate_report_draft(
                {"components": [{"componentId": "comp_chart"}]},
                [chart],
            )

        self.assertEqual(caught.exception.code, ErrorCode.LAYOUT_GENERATION_INVALID)
        self.assertIn("exactly one chart placeholder", str(caught.exception))

    def test_rejects_layout_without_document_local_css(self):
        from report_engine.errors import ErrorCode, ReportEngineError
        from report_engine.stage3_layout import Stage3LayoutService

        service = Stage3LayoutService(CssMissingAdapter())
        prompt_input = service.build_prompt_input(self.template, self.dataset, self.month_snapshot, self.components)

        with self.assertRaises(ReportEngineError) as caught:
            service.generate_report_draft(prompt_input, self.components)

        self.assertEqual(caught.exception.code, ErrorCode.LAYOUT_GENERATION_INVALID)
        self.assertIn("CSS", str(caught.exception))

    def test_rejects_layout_with_external_css_or_network_resource(self):
        from report_engine.errors import ErrorCode, ReportEngineError
        from report_engine.stage3_layout import Stage3LayoutService

        service = Stage3LayoutService(ExternalCssAdapter())
        prompt_input = service.build_prompt_input(self.template, self.dataset, self.month_snapshot, self.components)

        with self.assertRaises(ReportEngineError) as caught:
            service.generate_report_draft(prompt_input, self.components)

        self.assertEqual(caught.exception.code, ErrorCode.LAYOUT_GENERATION_INVALID)

    def test_rejects_layout_with_protocol_relative_network_resource(self):
        from report_engine.errors import ErrorCode, ReportEngineError
        from report_engine.stage3_layout import Stage3LayoutService

        service = Stage3LayoutService(ProtocolRelativeResourceAdapter())
        prompt_input = service.build_prompt_input(self.template, self.dataset, self.month_snapshot, self.components)

        with self.assertRaises(ReportEngineError) as caught:
            service.generate_report_draft(prompt_input, self.components)

        self.assertEqual(caught.exception.code, ErrorCode.LAYOUT_GENERATION_INVALID)

    def test_rejects_layout_that_renders_chart_before_stage4(self):
        from report_engine.errors import ErrorCode, ReportEngineError
        from report_engine.stage3_layout import Stage3LayoutService

        service = Stage3LayoutService(ChartRenderingAdapter())
        prompt_input = service.build_prompt_input(self.template, self.dataset, self.month_snapshot, self.components)

        with self.assertRaises(ReportEngineError) as caught:
            service.generate_report_draft(prompt_input, self.components)

        self.assertEqual(caught.exception.code, ErrorCode.LAYOUT_GENERATION_INVALID)

    def test_accepts_non_chart_inline_svg_decoration(self):
        from report_engine.models import Stage2Component
        from report_engine.stage3_layout import Stage3LayoutService

        chart = Stage2Component(
            componentId="comp_chart",
            dataSourceId="ds_chart",
            datasetId="data_x",
            monthId="2026-03",
            componentKey="performance_chart",
            renderType="chart",
            html='<section data-component-id="comp_chart"><div data-chart-placeholder="comp_chart"></div></section>',
            chartSpec={"type": "line"},
            styled=False,
        )
        summary = Stage2Component(
            componentId="comp_summary",
            dataSourceId="ds_summary",
            datasetId="data_x",
            monthId="2026-03",
            componentKey="performance_summary",
            renderType="table",
            html='<section data-component-id="comp_summary"><p>Preserve this summary value 12.34</p></section>',
            chartSpec=None,
            styled=False,
        )

        html = Stage3LayoutService(NonChartSvgDecorationAdapter()).generate_report_draft(
            {"components": [{"componentId": "comp_chart"}, {"componentId": "comp_summary"}]},
            [chart, summary],
        )

        self.assertIn("<svg", html)
        self.assertIn('data-chart-placeholder="comp_chart"', html)
        self.assertIn("Preserve this summary value 12.34", html)

    def test_rejects_svg_inside_chart_placeholder(self):
        from report_engine.errors import ErrorCode, ReportEngineError
        from report_engine.models import Stage2Component
        from report_engine.stage3_layout import Stage3LayoutService

        chart = Stage2Component(
            componentId="comp_chart",
            dataSourceId="ds_chart",
            datasetId="data_x",
            monthId="2026-03",
            componentKey="performance_chart",
            renderType="chart",
            html='<section data-component-id="comp_chart"><div data-chart-placeholder="comp_chart"></div></section>',
            chartSpec={"type": "line"},
            styled=False,
        )

        with self.assertRaises(ReportEngineError) as caught:
            Stage3LayoutService(ChartPlaceholderSvgAdapter()).generate_report_draft(
                {"components": [{"componentId": "comp_chart"}]},
                [chart],
            )

        self.assertEqual(caught.exception.code, ErrorCode.LAYOUT_GENERATION_INVALID)
        self.assertIn("render charts", str(caught.exception))

    def test_rejects_data_chart_rendered_svg_outside_chart_scope(self):
        from report_engine.errors import ErrorCode, ReportEngineError
        from report_engine.models import Stage2Component
        from report_engine.stage3_layout import Stage3LayoutService

        chart = Stage2Component(
            componentId="comp_chart",
            dataSourceId="ds_chart",
            datasetId="data_x",
            monthId="2026-03",
            componentKey="performance_chart",
            renderType="chart",
            html='<section data-component-id="comp_chart"><div data-chart-placeholder="comp_chart"></div></section>',
            chartSpec={"type": "line"},
            styled=False,
        )

        with self.assertRaises(ReportEngineError) as caught:
            Stage3LayoutService(DataChartRenderedSvgAdapter()).generate_report_draft(
                {"components": [{"componentId": "comp_chart"}]},
                [chart],
            )

        self.assertEqual(caught.exception.code, ErrorCode.LAYOUT_GENERATION_INVALID)
        self.assertIn("render charts", str(caught.exception))

    def test_rejects_unsafe_woori_revision_layout_patterns(self):
        from report_engine.errors import ErrorCode, ReportEngineError
        from report_engine.stage1_template import Stage1TemplateService
        from report_engine.stage3_layout import Stage3LayoutService

        woori_template = Stage1TemplateService(self.repository).load_template_context("tpl_woori_monthly_report")
        service = Stage3LayoutService(WooriUnsafeRevisionAdapter())
        prompt_input = service.build_prompt_input(woori_template, self.dataset, self.month_snapshot, self.components)
        prompt_input["verificationCorrection"] = {
            "revisionMode": "minimal_patch",
            "baseVersion": 1,
            "nextVersion": 2,
        }

        with self.assertRaises(ReportEngineError) as caught:
            service.generate_report_draft(prompt_input, self.components)

        self.assertEqual(caught.exception.code, ErrorCode.LAYOUT_GENERATION_INVALID)
        self.assertIn("Woori revision safety", str(caught.exception))

    def test_allows_grid_template_columns_in_woori_revision(self):
        from report_engine.stage1_template import Stage1TemplateService
        from report_engine.stage3_layout import Stage3LayoutService

        woori_template = Stage1TemplateService(self.repository).load_template_context("tpl_woori_monthly_report")
        service = Stage3LayoutService(WooriSafeGridRevisionAdapter())
        prompt_input = service.build_prompt_input(woori_template, self.dataset, self.month_snapshot, self.components)
        prompt_input["verificationCorrection"] = {
            "revisionMode": "minimal_patch",
            "baseVersion": 1,
            "nextVersion": 2,
        }

        html = service.generate_report_draft(prompt_input, self.components)

        self.assertIn("grid-template-columns", html)
        self.assertIn("data-chart-placeholder", html)

    def test_rejects_layout_with_absolute_footer_overlap_risk(self):
        from report_engine.errors import ErrorCode, ReportEngineError
        from report_engine.stage3_layout import Stage3LayoutService

        service = Stage3LayoutService(AbsoluteFooterAdapter())
        prompt_input = service.build_prompt_input(self.template, self.dataset, self.month_snapshot, self.components)

        with self.assertRaises(ReportEngineError) as caught:
            service.generate_report_draft(prompt_input, self.components)

        self.assertEqual(caught.exception.code, ErrorCode.LAYOUT_GENERATION_INVALID)

    def test_allows_non_footer_selector_absolute_position_for_decorative_markers(self):
        from report_engine.stage3_layout import Stage3LayoutService

        service = Stage3LayoutService(TableFooterMarkerAdapter())
        prompt_input = service.build_prompt_input(self.template, self.dataset, self.month_snapshot, self.components)

        html = service.generate_report_draft(prompt_input, self.components)

        self.assertIn(".table-footer ul li::before", html)
        self.assertIn("position: absolute", html)
        self.assertIn("<footer>normal flow disclaimer</footer>", html)

    def test_rejects_layout_missing_component_id(self):
        from report_engine.errors import ErrorCode, ReportEngineError
        from report_engine.stage3_layout import Stage3LayoutService

        service = Stage3LayoutService(MissingComponentAdapter())
        prompt_input = service.build_prompt_input(self.template, self.dataset, self.month_snapshot, self.components)

        with self.assertRaises(ReportEngineError) as caught:
            service.generate_report_draft(prompt_input, self.components)

        self.assertEqual(caught.exception.code, ErrorCode.LAYOUT_GENERATION_INVALID)

    def test_rejects_layout_with_component_id_only_in_text(self):
        from report_engine.errors import ErrorCode, ReportEngineError
        from report_engine.models import Stage2Component
        from report_engine.stage3_layout import Stage3LayoutService

        component = Stage2Component(
            componentId="comp_article",
            dataSourceId="ds_article",
            datasetId="data_x",
            monthId="2026-03",
            componentKey="review",
            renderType="article",
            html='<section data-component-id="comp_article"><p>Preserve this article text.</p></section>',
            chartSpec=None,
            styled=False,
        )
        service = Stage3LayoutService(TextOnlyComponentIdAdapter())
        prompt_input = {
            "components": [
                {
                    "componentId": component.componentId,
                    "html": component.html,
                }
            ]
        }

        with self.assertRaises(ReportEngineError) as caught:
            service.generate_report_draft(prompt_input, [component])

        self.assertEqual(caught.exception.code, ErrorCode.LAYOUT_GENERATION_INVALID)
        self.assertIn("missing components", str(caught.exception))

    def test_rejects_component_id_only_in_css_selector(self):
        from report_engine.errors import ErrorCode, ReportEngineError
        from report_engine.models import Stage2Component
        from report_engine.stage3_layout import Stage3LayoutService

        component = Stage2Component(
            componentId="comp_article",
            dataSourceId="ds_article",
            datasetId="data_x",
            monthId="2026-03",
            componentKey="review",
            renderType="article",
            html='<section data-component-id="comp_article"><p>Preserve this article text.</p></section>',
            chartSpec=None,
            styled=False,
        )

        with self.assertRaises(ReportEngineError) as caught:
            Stage3LayoutService(CssOnlyComponentIdAdapter()).generate_report_draft(
                {"components": [{"componentId": component.componentId, "html": component.html}]},
                [component],
            )

        self.assertEqual(caught.exception.code, ErrorCode.LAYOUT_GENERATION_INVALID)
        self.assertIn("missing components", str(caught.exception))

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
    def generate_stage3_layout(self, prompt_input, template_image_data_url=None):
        self.last_prompt_input = prompt_input
        body = "\n".join(item["html"] for item in prompt_input["components"])
        return f"<!doctype html><html><head><style>{_TEMPLATE_CSS_VARS} body {{ margin: 0; }}</style></head><body>{body}</body></html>"


class _SequenceLayoutAdapter:
    def __init__(self):
        self.call_count = 0
        self.prompt_inputs = []
        self.template_image_data_urls = []

    def generate_stage3_layout(self, prompt_input, template_image_data_url=None):
        self.call_count += 1
        self.prompt_inputs.append(prompt_input)
        self.template_image_data_urls.append(template_image_data_url)
        return self._response(prompt_input, self.call_count)

    def _response(self, prompt_input, call_count):
        raise NotImplementedError

    @staticmethod
    def _valid_html(prompt_input):
        body = "\n".join(item["html"] for item in prompt_input["components"])
        return f"<!doctype html><html><head><style>{_TEMPLATE_CSS_VARS} body {{ margin: 0; }}</style></head><body>{body}</body></html>"


class CssMissingThenValidAdapter(_SequenceLayoutAdapter):
    def _response(self, prompt_input, call_count):
        if call_count == 1:
            body = "\n".join(item["html"] for item in prompt_input["components"])
            return f"<!doctype html><html><body>{body}</body></html>"
        return self._valid_html(prompt_input)


class CssVariablesMissingThenValidAdapter(_SequenceLayoutAdapter):
    def _response(self, prompt_input, call_count):
        body = "\n".join(item["html"] for item in prompt_input["components"])
        if call_count == 1:
            return f"<!doctype html><html><head><style>body {{ margin: 0; }}</style></head><body>{body}</body></html>"
        return self._valid_html(prompt_input)


class SourceMissingThenValidAdapter(_SequenceLayoutAdapter):
    def _response(self, prompt_input, call_count):
        if call_count == 1:
            body = "\n".join(
                item["html"].replace("NVIDIA Corp", "")
                for item in prompt_input["components"]
            )
            return f"<!doctype html><html><head><style>{_TEMPLATE_CSS_VARS} body {{ margin: 0; }}</style></head><body>{body}</body></html>"
        return self._valid_html(prompt_input)


class FooterAbsoluteThenValidAdapter(_SequenceLayoutAdapter):
    def _response(self, prompt_input, call_count):
        body = "\n".join(item["html"] for item in prompt_input["components"])
        if call_count == 1:
            return (
                "<!doctype html><html><head><style>"
                f"{_TEMPLATE_CSS_VARS} body {{ margin: 0; }} footer {{ position: absolute; bottom: 0; left: 0; right: 0; }}"
                "</style></head><body>"
                f"{body}<footer>normal flow disclaimer</footer>"
                "</body></html>"
            )
        return self._valid_html(prompt_input) + "<footer>normal flow disclaimer</footer>"


class PercentMissingThenStructuredCorrectionAdapter(_SequenceLayoutAdapter):
    def _response(self, prompt_input, call_count):
        source_body = "\n".join(item["html"] for item in prompt_input["components"])
        bad_body = (
            source_body
            .replace("-4.89%", "-4.89")
            .replace("6.65%", "6.65")
            .replace("9.55%", "9.55")
        )
        if call_count == 1:
            return f"<!doctype html><html><head><style>{_TEMPLATE_CSS_VARS} body {{ margin: 0; }}</style></head><body>{bad_body}</body></html>"
        correction = prompt_input.get("correction", {})
        if isinstance(correction, dict) and correction.get("sourceFragmentViolations"):
            return self._valid_html(prompt_input)
        return f"<!doctype html><html><head><style>{_TEMPLATE_CSS_VARS} body {{ margin: 0; }}</style></head><body>{bad_body}</body></html>"


class WooriFragmentsValidOnFourthCallAdapter(_SequenceLayoutAdapter):
    def _response(self, prompt_input, call_count):
        source_body = "\n".join(item["html"] for item in prompt_input["components"])
        bad_body = (
            source_body
            .replace("-4.89%", "-4.89")
            .replace("6.65%", "6.65")
            .replace("9.55%", "9.55")
            .replace("자료 : 삼성자산운용, 2026.03.31 기준", "자료 : 삼성자산운용, 2026년 3월 31일 기준")
        )
        if call_count < 4:
            return f"<!doctype html><html><head><style>{_TEMPLATE_CSS_VARS} body {{ margin: 0; }}</style></head><body>{bad_body}</body></html>"
        return self._valid_html(prompt_input)


class KbFragmentsAlwaysInvalidAdapter(_SequenceLayoutAdapter):
    def _response(self, prompt_input, call_count):
        source_body = "\n".join(item["html"] for item in prompt_input["components"])
        bad_body = (
            source_body
            .replace("<th>6개월</th>", "<th>6M</th>")
            .replace("<th>1년</th>", "<th>1Y</th>")
            .replace("<th>연초후</th>", "<th>YTD</th>")
            .replace("0.56%", "0.56")
            .replace("19.09%", "19.09")
            .replace("<th>No.</th>", "")
            .replace("<th>보유비중(%)</th>", "<th>비중(%)</th>")
            .replace('<tr><td colspan="2">합계</td><td>37.37</td></tr>', "")
        )
        return f"<!doctype html><html><head><style>{_TEMPLATE_CSS_VARS} body {{ margin: 0; }}</style></head><body>{bad_body}</body></html>"


class AlwaysCssMissingAdapter(_SequenceLayoutAdapter):
    def _response(self, prompt_input, call_count):
        body = "\n".join(item["html"] for item in prompt_input["components"])
        return f"<!doctype html><html><body>{body}</body></html>"


class CssMissingAdapter:
    def generate_stage3_layout(self, prompt_input, template_image_data_url=None):
        body = "\n".join(item["html"] for item in prompt_input["components"])
        return f"<!doctype html><html><body>{body}</body></html>"


class ExternalCssAdapter:
    def generate_stage3_layout(self, prompt_input, template_image_data_url=None):
        body = "\n".join(item["html"] for item in prompt_input["components"])
        return (
            '<!doctype html><html><head><link rel="stylesheet" href="https://example.com/report.css">'
            f"<style>@import url('https://example.com/theme.css'); {_TEMPLATE_CSS_VARS} body {{ margin: 0; }}</style></head>"
            f"<body>{body}</body></html>"
        )


class ProtocolRelativeResourceAdapter:
    def generate_stage3_layout(self, prompt_input, template_image_data_url=None):
        body = "\n".join(item["html"] for item in prompt_input["components"])
        return (
            f"<!doctype html><html><head><style>{_TEMPLATE_CSS_VARS} body {{ margin: 0; }}</style></head>"
            f'<body>{body}<img src="//example.com/report.png" alt=""></body></html>'
        )


class SourceMissingAdapter:
    def generate_stage3_layout(self, prompt_input, template_image_data_url=None):
        body = "\n".join(
            item["html"].replace("NVIDIA Corp", "")
            for item in prompt_input["components"]
        )
        return f"<!doctype html><html><head><style>{_TEMPLATE_CSS_VARS} body {{ margin: 0; }}</style></head><body>{body}</body></html>"


class HeadingRelabeledAdapter:
    def generate_stage3_layout(self, prompt_input, template_image_data_url=None):
        body = prompt_input["components"][0]["html"].replace("ETF 성과 추이 요약", "ETF 성과 추이")
        return f"<!doctype html><html><head><style>{_TEMPLATE_CSS_VARS} body {{ margin: 0; }}</style></head><body>{body}</body></html>"


class MissingTableHeaderAdapter:
    def generate_stage3_layout(self, prompt_input, template_image_data_url=None):
        body = prompt_input["components"][0]["html"].replace("<th>1개월</th>", "")
        return f"<!doctype html><html><head><style>{_TEMPLATE_CSS_VARS} body {{ margin: 0; }}</style></head><body>{body}</body></html>"


class MissingTableNumberAdapter:
    def generate_stage3_layout(self, prompt_input, template_image_data_url=None):
        body = prompt_input["components"][0]["html"].replace("<td>6.45%</td>", "")
        return f"<!doctype html><html><head><style>{_TEMPLATE_CSS_VARS} body {{ margin: 0; }}</style></head><body>{body}</body></html>"


class MissingListItemAdapter:
    def generate_stage3_layout(self, prompt_input, template_image_data_url=None):
        body = prompt_input["components"][0]["html"].replace("<li>BM : NASDAQ 100 Index</li>", "")
        return f"<!doctype html><html><head><style>body {{ margin: 0; }}</style></head><body>{body}</body></html>"


class ListMarkerMovedAdapter:
    def generate_stage3_layout(self, prompt_input, template_image_data_url=None):
        return (
            f'<!doctype html><html><head><style>{_TEMPLATE_CSS_VARS} body {{ margin: 0; }}</style></head><body>'
            '<section data-component-id="comp_outlook">'
            '<ul>'
            '<li data-num="1">NVIDIA와 BROADCOM을 중심으로 한 AI 반도체 수요가 지수 성과의 핵심 동력으로 작용할 전망</li>'
            '<li data-num="2">대형 플랫폼 기업의 광고, 클라우드, 구독 매출 회복이 <strong>이익 안정성</strong>을 높일 가능성</li>'
            '<li data-num="3">높은 성장주 집중도는 금리 상승 또는 규제 이슈 발생 시 단기 조정 폭을 키울 수 있음</li>'
            '</ul>'
            '</section>'
            '</body></html>'
        )


class ChartPlaceholderOnlyAdapter:
    def generate_stage3_layout(self, prompt_input, template_image_data_url=None):
        return (
            f'<!doctype html><html><head><style>{_TEMPLATE_CSS_VARS} body {{ margin: 0; }}</style></head><body>'
            '<section data-component-id="comp_chart"><div data-chart-placeholder="comp_chart"></div></section>'
            '<section data-component-id="comp_summary"><p>Preserve this summary value 12.34</p></section>'
            "</body></html>"
        )


class ChartPlaceholderWithoutComponentIdAdapter:
    def generate_stage3_layout(self, prompt_input, template_image_data_url=None):
        return (
            f'<!doctype html><html><head><style>{_TEMPLATE_CSS_VARS} body {{ margin: 0; }}</style></head><body>'
            '<div class="chart-placeholder" data-chart-placeholder="comp_chart">Chart placeholder</div>'
            '<section data-component-id="comp_summary"><p>Preserve this summary value 12.34</p></section>'
            "</body></html>"
        )


class ChartPlaceholderWithExactCssSelectorAdapter:
    def generate_stage3_layout(self, prompt_input, template_image_data_url=None):
        return (
            '<!doctype html><html><head><style>'
            f'{_TEMPLATE_CSS_VARS} [data-chart-placeholder="comp_chart"] {{ min-height: 120px; }}'
            "</style></head><body>"
            '<div class="chart-placeholder" data-chart-placeholder="comp_chart">Chart placeholder</div>'
            "</body></html>"
        )


class ChartComponentWithoutPlaceholderAdapter:
    def generate_stage3_layout(self, prompt_input, template_image_data_url=None):
        return (
            f'<!doctype html><html><head><style>{_TEMPLATE_CSS_VARS} body {{ margin: 0; }}</style></head><body>'
            '<section data-component-id="comp_chart"><div class="chart-placeholder">Chart placeholder</div></section>'
            "</body></html>"
        )


class DuplicateChartPlaceholderAdapter:
    def generate_stage3_layout(self, prompt_input, template_image_data_url=None):
        return (
            f'<!doctype html><html><head><style>{_TEMPLATE_CSS_VARS} body {{ margin: 0; }}</style></head><body>'
            '<section data-component-id="comp_chart">'
            '<div data-chart-placeholder="comp_chart">Chart placeholder 1</div>'
            '<div data-chart-placeholder="comp_chart">Chart placeholder 2</div>'
            "</section>"
            "</body></html>"
        )


def _preservation_component():
    from report_engine.models import Stage2Component

    return Stage2Component(
        componentId="comp_summary",
        dataSourceId="ds_summary",
        datasetId="data_x",
        monthId="2026-03",
        componentKey="performance_summary",
        renderType="table",
        html=(
            '<section data-component-id="comp_summary">'
            "<h2>ETF 성과 추이 요약</h2>"
            "<table><thead><tr><th>1개월</th><th>3개월</th></tr></thead>"
            "<tbody><tr><td>6.45%</td><td>16.72%</td></tr></tbody></table>"
            "<ul><li>BM : NASDAQ 100 Index</li></ul>"
            "<p>과거수익률이 미래성과를 보장하지 않습니다.</p>"
            "</section>"
        ),
        chartSpec=None,
        styled=False,
    )


def _woori_live_failure_component():
    from report_engine.models import Stage2Component

    return Stage2Component(
        componentId="comp_summary",
        dataSourceId="ds_summary",
        datasetId="data_x",
        monthId="2026-03",
        componentKey="performance_summary",
        renderType="table",
        html=(
            '<section data-component-id="comp_summary">'
            "<table><tbody><tr>"
            "<td>-4.89%</td><td>6.65%</td><td>9.55%</td>"
            "</tr></tbody></table>"
            "<p>자료 : 삼성자산운용, 2026.03.31 기준</p>"
            "</section>"
        ),
        chartSpec=None,
        styled=False,
    )


def _kb_repair_component():
    from report_engine.models import Stage2Component

    return Stage2Component(
        componentId="comp_kb_summary",
        dataSourceId="ds_kb_summary",
        datasetId="data_x",
        monthId="2026-03",
        componentKey="performance_summary",
        renderType="table",
        html=(
            '<section data-component-id="comp_kb_summary">'
            "<h2>ETF 성과 추이 요약</h2>"
            "<table><thead><tr><th></th><th>1개월</th><th>3개월</th><th>6개월</th><th>1년</th><th>연초후</th></tr></thead>"
            "<tbody><tr><td>수익률</td><td>5.95%</td><td>11.97%</td><td>0.56%</td><td>19.09%</td><td>11.97%</td></tr></tbody></table>"
            "<table><thead><tr><th>No.</th><th>종목명</th><th>보유비중(%)</th></tr></thead>"
            "<tbody><tr><td>1</td><td>NVIDIA Corp</td><td>7.93</td></tr><tr><td colspan=\"2\">합계</td><td>37.37</td></tr></tbody></table>"
            "</section>"
        ),
        chartSpec=None,
        styled=False,
    )


class MissingComponentAdapter:
    def generate_stage3_layout(self, prompt_input, template_image_data_url=None):
        body = "\n".join(
            f'<section data-component-id="{item["componentId"]}"></section>'
            for item in prompt_input["components"][:-1]
        )
        return f"<!doctype html><html><head><style>{_TEMPLATE_CSS_VARS} body {{ margin: 0; }}</style></head><body>{body}</body></html>"


class TextOnlyComponentIdAdapter:
    def generate_stage3_layout(self, prompt_input, template_image_data_url=None):
        body_parts = []
        for index, item in enumerate(prompt_input["components"]):
            if index:
                body_parts.append(item["html"])
                continue
            marker = f'data-component-id="{item["componentId"]}"'
            component_html = item["html"].replace(marker, 'data-removed-component-id="x"')
            body_parts.append(f'<section><p>{item["componentId"]}</p>{component_html}</section>')
        body = "\n".join(body_parts)
        return f"<!doctype html><html><head><style>{_TEMPLATE_CSS_VARS} body {{ margin: 0; }}</style></head><body>{body}</body></html>"


class CssOnlyComponentIdAdapter:
    def generate_stage3_layout(self, prompt_input, template_image_data_url=None):
        return (
            '<!doctype html><html><head><style>'
            f'{_TEMPLATE_CSS_VARS} [data-component-id="comp_article"] {{ margin: 0; }}'
            "</style></head><body>"
            "<section><p>Preserve this article text.</p></section>"
            "</body></html>"
        )


class FencedHtmlAdapter:
    def generate_stage3_layout(self, prompt_input, template_image_data_url=None):
        body = "\n".join(item["html"] for item in prompt_input["components"])
        return f"```html\n<!doctype html><html><head><style>{_TEMPLATE_CSS_VARS} body {{ margin: 0; }}</style></head><body>{body}</body></html>\n```"


class ChartRenderingAdapter:
    def generate_stage3_layout(self, prompt_input, template_image_data_url=None):
        body = "\n".join(
            f'<section data-component-id="{component_id}"><svg><rect width="1" height="1"></rect></svg></section>'
            if item["renderType"] == "chart"
            else item["html"]
            for item in prompt_input["components"]
            for component_id in [item["componentId"]]
        )
        return f"<!doctype html><html><head><style>{_TEMPLATE_CSS_VARS} body {{ margin: 0; }}</style></head><body>{body}</body></html>"


class NonChartSvgDecorationAdapter:
    def generate_stage3_layout(self, prompt_input, template_image_data_url=None):
        return (
            f'<!doctype html><html><head><style>{_TEMPLATE_CSS_VARS} body {{ margin: 0; }}</style></head><body>'
            '<header><svg viewBox="0 0 10 10"><rect width="10" height="10"></rect></svg></header>'
            '<main>'
            '<div data-chart-placeholder="comp_chart">Chart placeholder</div>'
            '<section data-component-id="comp_summary"><p>Preserve this summary value 12.34</p></section>'
            '</main>'
            '</body></html>'
        )


class ChartPlaceholderSvgAdapter:
    def generate_stage3_layout(self, prompt_input, template_image_data_url=None):
        return (
            f'<!doctype html><html><head><style>{_TEMPLATE_CSS_VARS} body {{ margin: 0; }}</style></head><body>'
            '<div data-chart-placeholder="comp_chart">'
            '<svg viewBox="0 0 10 10"><polyline points="0,10 10,0"></polyline></svg>'
            '</div>'
            '</body></html>'
        )


class DataChartRenderedSvgAdapter:
    def generate_stage3_layout(self, prompt_input, template_image_data_url=None):
        return (
            f'<!doctype html><html><head><style>{_TEMPLATE_CSS_VARS} body {{ margin: 0; }}</style></head><body>'
            '<div data-chart-placeholder="comp_chart">Chart placeholder</div>'
            '<svg data-chart-rendered="performance_chart" viewBox="0 0 10 10"></svg>'
            '</body></html>'
        )


class WooriUnsafeRevisionAdapter:
    def generate_stage3_layout(self, prompt_input, template_image_data_url=None):
        body = "\n".join(item["html"] for item in prompt_input["components"])
        chart_id = prompt_input["components"][0]["componentId"]
        body = body.replace(
            f'<div data-chart-placeholder="{chart_id}"></div>',
            f'<div data-chart-placeholder="{chart_id}"><div class="chart-visual-mock"></div></div>',
        )
        return (
            "<!doctype html><html><head><style>"
            f"{_TEMPLATE_CSS_VARS} body {{ margin: 0; }}"
            ".text-section { columns: 2; }"
            ".outlook { writing-mode: vertical-rl; }"
            ".chart-visual-mock { display: flex; }"
            "</style></head><body>"
            f"{body}"
            "</body></html>"
        )


class WooriSafeGridRevisionAdapter:
    def generate_stage3_layout(self, prompt_input, template_image_data_url=None):
        body = "\n".join(item["html"] for item in prompt_input["components"])
        return (
            "<!doctype html><html><head><style>"
            f"{_TEMPLATE_CSS_VARS} body {{ margin: 0; }}"
            ".grid-container { display: grid; grid-template-columns: 1fr 1fr; }"
            "</style></head><body>"
            f"{body}"
            "</body></html>"
        )


class AbsoluteFooterAdapter:
    def generate_stage3_layout(self, prompt_input, template_image_data_url=None):
        body = "\n".join(item["html"] for item in prompt_input["components"])
        return (
            "<!doctype html><html><head><style>"
            f"{_TEMPLATE_CSS_VARS} footer {{ position: absolute; bottom: 20mm; left: 20mm; right: 20mm; }}"
            "</style></head><body>"
            f"{body}<footer>disclaimer</footer>"
            "</body></html>"
        )


class TableFooterMarkerAdapter:
    def generate_stage3_layout(self, prompt_input, template_image_data_url=None):
        body = "\n".join(item["html"] for item in prompt_input["components"])
        return (
            "<!doctype html><html><head><style>"
            f"{_TEMPLATE_CSS_VARS} body {{ margin: 0; }}"
            ".table-footer ul li { position: relative; padding-left: 14px; }"
            ".table-footer ul li::before { content: '•'; position: absolute; left: 0; }"
            "footer { padding: 20px 32px; margin-top: 24px; }"
            "</style></head><body>"
            f"{body}<footer>normal flow disclaimer</footer>"
            "</body></html>"
        )


def _write_default_stage3_prompt_files(prompt_root: Path) -> None:
    _write_prompt_json(
        prompt_root,
        "03_layout_visual_objective.json",
        [
            "Match the template preview image as closely as possible.",
            "Treat the template preview image as a visual reference only; do not use it as a source for report data, labels, numbers, or prose.",
            "Generate A4 portrait layout, typography, spacing, brand/header/footer styling, and section styling in Stage 3.",
        ],
    )
    _write_prompt_json(
        prompt_root,
        "03_layout_constraints.json",
        [
            "Return one complete HTML document.",
            "Match the template preview image as closely as possible.",
            "Infer the report palette, accent colors, header styling, table styling, and section styling from the attached template preview image.",
            "Define --report-primary, --report-accent, --chart-series-1, and --chart-series-2 CSS variables from the attached template preview image.",
            "Use supplied Stage 2 components as the only source for report data, table labels, values, and prose.",
            "Do not copy data labels, table values, or prose from template preview image.",
            "Generate document-local CSS in a non-empty <style> block.",
            "Do not use external CSS files, @import, external fonts, or external network resources.",
            "Stage 3 CSS must cover A4 portrait layout, header/footer/brand, section spacing, typography, table/list/article styling, chart placeholder space, and bottom safe area.",
            "Preserve every Stage 2 component id.",
            "Do not change source numbers or source wording.",
            "Do not reference external network resources.",
            "Do not render charts in Stage 3.",
            "Keep chart components as data-chart-placeholder containers only; Stage 4 renders chart assets.",
            "Do not render charts using SVG, canvas, script, Chart.js, or other chart rendering markup.",
            "Footer must stay in normal document flow.",
            "Do not use position:absolute or position:fixed for footer or bottom disclaimers.",
            "Reserve a bottom safe area so the final section never overlaps the footer.",
            "If content is long, reduce spacing or continue the normal page flow instead of overlapping footer text.",
        ],
    )
    _write_prompt_json(
        prompt_root,
        "03_layout_correction_requirements.json",
        [
            "Return one complete HTML document.",
            "Fix missing CSS, missing components, missing chart placeholders, omitted source fragments, chart rendering markup, and footer flow violations.",
            "Preserve every non-chart Stage 2 table header, table cell, paragraph, and list item exactly as visible text.",
            "Keep chart components as exact data-chart-placeholder containers only; do not render charts in Stage 3.",
            "Do not render charts using SVG, canvas, script, or Chart.js.",
            "Each chart component must include exactly one data-chart-placeholder attribute whose value is the componentId.",
            "Return raw HTML only; do not include Markdown fences or explanations.",
        ],
    )


def _write_prompt_json(prompt_root: Path, filename: str, value) -> None:
    _write_prompt_file(prompt_root, filename, json.dumps(value, ensure_ascii=False))


def _write_prompt_file(prompt_root: Path, filename: str, content: str) -> None:
    prompt_root.mkdir(parents=True, exist_ok=True)
    (prompt_root / filename).write_text(content, encoding="utf-8")


if __name__ == "__main__":
    unittest.main()
