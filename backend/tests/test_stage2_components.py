import unittest
from dataclasses import replace
from pathlib import Path
from threading import Lock
from time import sleep


BACKEND_ROOT = Path(__file__).resolve().parents[1]
WORKSPACE_ROOT = BACKEND_ROOT.parent
DATASET_IDS = [
    "data_kodex_us_sp500_h",
    "data_kodex_us_sp500",
    "data_kodex_us_nasdaq100",
    "data_kodex_korea_dividend_growth_bond_mixed",
]
MONTH_IDS = ["2026-01", "2026-02", "2026-03"]


class Stage2ComponentTests(unittest.TestCase):
    def setUp(self):
        from report_engine.repository import ReportRepository
        from report_engine.stage2_components import Stage2ComponentService

        self.repository = ReportRepository(WORKSPACE_ROOT)
        self.service = Stage2ComponentService(self.repository)

    def test_sample_mode_returns_five_ordered_unstyled_components_for_all_dataset_months(self):
        for dataset_id in DATASET_IDS:
            for month_id in MONTH_IDS:
                with self.subTest(dataset_id=dataset_id, month_id=month_id):
                    components = self.service.load_components(dataset_id, month_id, component_mode="sample")
                    self.assertEqual([item.componentKey for item in components], self.service.COMPONENT_KEYS)
                    self.assertEqual(len(components), 5)
                    self.assertTrue(components[0].chartSpec)
                    for component in components[1:]:
                        self.assertIsNone(component.chartSpec)

    def test_rejects_style_class_and_style_tags(self):
        from report_engine.errors import ErrorCode, ReportEngineError

        components = self.service.load_components("data_kodex_us_sp500", "2026-03", component_mode="sample")
        broken = replace(components[0], html='<section class="bad"></section>')

        with self.assertRaises(ReportEngineError) as caught:
            self.service.validate_components([broken, *components[1:]])
        self.assertEqual(caught.exception.code, ErrorCode.COMPONENT_SOURCE_INCOMPLETE)

    def test_novita_mode_uses_fake_adapter_to_generate_ordered_components(self):
        from report_engine.stage2_components import Stage2ComponentService

        fake_adapter = FakeLlmAdapter()
        service = Stage2ComponentService(self.repository, llm_adapter=fake_adapter)

        components = service.load_components("data_kodex_us_sp500", "2026-03", component_mode="novita")

        self.assertEqual([item.componentKey for item in components], self.service.COMPONENT_KEYS)
        self.assertCountEqual([item["componentKey"] for item in fake_adapter.stage2_calls], self.service.COMPONENT_KEYS)
        calls_by_key = {item["componentKey"]: item for item in fake_adapter.stage2_calls}
        self.assertEqual(
            calls_by_key["performance_chart"]["componentId"],
            "comp_data_kodex_us_sp500_2026_03_performance_chart",
        )
        self.assertEqual(components[0].componentId, "comp_data_kodex_us_sp500_2026_03_performance_chart")
        self.assertEqual(components[0].dataSourceId, "ds_data_kodex_us_sp500_2026_03_performance_chart")
        self.assertTrue(components[0].chartSpec)
        for component in components:
            self.assertIn(f'data-component-id="{component.componentId}"', component.html)
            self.assertFalse(component.styled)
        for component in components[1:]:
            self.assertIsNone(component.chartSpec)

    def test_novita_mode_calls_component_llm_in_parallel_and_returns_key_order(self):
        from report_engine.stage2_components import Stage2ComponentService

        fake_adapter = SlowOutOfOrderLlmAdapter()
        service = Stage2ComponentService(self.repository, llm_adapter=fake_adapter)

        components = service.load_components("data_kodex_us_sp500", "2026-03", component_mode="novita")

        self.assertGreater(fake_adapter.max_active_calls, 1)
        self.assertNotEqual(fake_adapter.completed_component_keys, self.service.COMPONENT_KEYS)
        self.assertEqual([item.componentKey for item in components], self.service.COMPONENT_KEYS)

    def test_rejects_missing_component_id_marker(self):
        from report_engine.errors import ErrorCode, ReportEngineError

        components = self.service.load_components("data_kodex_us_sp500", "2026-03", component_mode="sample")
        broken = replace(components[0], html="<section><p>missing marker</p></section>")

        with self.assertRaises(ReportEngineError) as caught:
            self.service.validate_components([broken, *components[1:]])
        self.assertEqual(caught.exception.code, ErrorCode.COMPONENT_SOURCE_INCOMPLETE)

    def test_rejects_component_id_marker_only_in_text(self):
        from report_engine.errors import ErrorCode, ReportEngineError

        components = self.service.load_components("data_kodex_us_sp500", "2026-03", component_mode="sample")
        broken = replace(
            components[0],
            html=f'<section><p>data-component-id="{components[0].componentId}"</p></section>',
        )

        with self.assertRaises(ReportEngineError) as caught:
            self.service.validate_components([broken, *components[1:]])
        self.assertEqual(caught.exception.code, ErrorCode.COMPONENT_SOURCE_INCOMPLETE)

    def test_rejects_component_id_marker_inside_other_attribute_value(self):
        from report_engine.errors import ErrorCode, ReportEngineError

        components = self.service.load_components("data_kodex_us_sp500", "2026-03", component_mode="sample")
        broken = replace(
            components[0],
            html=f'<section title=\'data-component-id="{components[0].componentId}"\'></section>',
        )

        with self.assertRaises(ReportEngineError) as caught:
            self.service.validate_components([broken, *components[1:]])
        self.assertEqual(caught.exception.code, ErrorCode.COMPONENT_SOURCE_INCOMPLETE)


class FakeLlmAdapter:
    def __init__(self):
        self.stage2_calls = []

    def generate_stage2_component(self, component_source):
        self.stage2_calls.append(component_source)
        dataset_id = component_source["datasetRef"]["datasetId"]
        month_id = component_source["snapshotRef"]["monthId"]
        component_key = component_source["componentKey"]
        component_id = f"comp_{dataset_id}_{month_id.replace('-', '_')}_{component_key}"
        chart_spec = {"type": "line", "source": component_source["dataSourceId"]} if component_key == "performance_chart" else None
        return {
            "html": f'<section data-component-id="{component_id}"><h2>{component_source["title"]}</h2></section>',
            "chartSpec": chart_spec,
            "styled": False,
        }

    def generate_stage3_layout(self, prompt_input, template_image_data_url=None):
        component_ids = [item["componentId"] for item in prompt_input["components"]]
        body = "\n".join(f'<section data-component-id="{component_id}"></section>' for component_id in component_ids)
        return f"<!doctype html><html><head><style>body {{ margin: 0; }}</style></head><body>{body}</body></html>"


class SlowOutOfOrderLlmAdapter:
    DELAYS_BY_KEY = {
        "performance_chart": 0.05,
        "performance_summary": 0.04,
        "top_holdings": 0.03,
        "review": 0.02,
        "outlook": 0.01,
    }

    def __init__(self):
        self.active_calls = 0
        self.max_active_calls = 0
        self.completed_component_keys = []
        self.lock = Lock()

    def generate_stage2_component(self, component_source):
        component_key = component_source["componentKey"]
        with self.lock:
            self.active_calls += 1
            self.max_active_calls = max(self.max_active_calls, self.active_calls)
        try:
            sleep(self.DELAYS_BY_KEY[component_key])
            dataset_id = component_source["datasetRef"]["datasetId"]
            month_id = component_source["snapshotRef"]["monthId"]
            component_id = f"comp_{dataset_id}_{month_id.replace('-', '_')}_{component_key}"
            chart_spec = {"type": "line"} if component_key == "performance_chart" else None
            return {
                "html": f'<section data-component-id="{component_id}"><h2>{component_key}</h2></section>',
                "chartSpec": chart_spec,
                "styled": False,
            }
        finally:
            with self.lock:
                self.completed_component_keys.append(component_key)
                self.active_calls -= 1


if __name__ == "__main__":
    unittest.main()
