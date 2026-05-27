import unittest
from dataclasses import replace
from pathlib import Path


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

        self.service = Stage2ComponentService(ReportRepository(WORKSPACE_ROOT))

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

    def test_rejects_novita_mode_for_task_5_scope(self):
        from report_engine.errors import ErrorCode, ReportEngineError

        with self.assertRaises(ReportEngineError) as caught:
            self.service.load_components("data_kodex_us_sp500", "2026-03", component_mode="novita")
        self.assertEqual(caught.exception.code, ErrorCode.COMPONENT_SOURCE_INCOMPLETE)


if __name__ == "__main__":
    unittest.main()
