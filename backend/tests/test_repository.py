import unittest
from pathlib import Path


BACKEND_ROOT = Path(__file__).resolve().parents[1]
WORKSPACE_ROOT = BACKEND_ROOT.parent


class RepositoryTests(unittest.TestCase):
    def setUp(self):
        from report_engine.repository import ReportRepository

        self.repository = ReportRepository(WORKSPACE_ROOT)

    def test_loads_dataset_and_template_independently(self):
        dataset = self.repository.load_dataset("data_kodex_us_sp500")
        kb_template = self.repository.load_template("tpl_kb_monthly_guidebook")
        woori_template = self.repository.load_template("tpl_woori_monthly_report")

        self.assertEqual(dataset.datasetId, "data_kodex_us_sp500")
        self.assertFalse(hasattr(dataset, "styleCandidates"))
        self.assertEqual(kb_template.templateId, "tpl_kb_monthly_guidebook")
        self.assertEqual(woori_template.templateId, "tpl_woori_monthly_report")
        self.assertFalse(hasattr(kb_template, "sourceHtml"))
        self.assertEqual(kb_template.previewImage, "backend/data/report_template/국민은행_월간_리포트.png")
        self.assertFalse(hasattr(woori_template, "sourceHtml"))
        self.assertEqual(woori_template.previewImage, "backend/data/report_template/우리은행_월간_리포트.png")
        self.assertFalse(kb_template.chartProfile["performance_chart"].templateImageHasChart)
        self.assertIsNone(kb_template.chartProfile["performance_chart"].detectedChartType)
        self.assertEqual(kb_template.chartProfile["performance_chart"].fallbackChartType, "bar")
        self.assertTrue(woori_template.chartProfile["performance_chart"].templateImageHasChart)
        self.assertEqual(woori_template.chartProfile["performance_chart"].detectedChartType, "bar")
        self.assertEqual(woori_template.chartProfile["performance_chart"].fallbackChartType, "bar")
        self.assertTrue(woori_template.revisionProfile.preserveInitialGrid)
        self.assertEqual(woori_template.revisionProfile.revisionMode, "minimal_patch")
        self.assertEqual(woori_template.revisionProfile.maxPreviewDimensionDriftRatio, 0.15)
        self.assertIn("header", woori_template.revisionProfile.allowedRevisionTargets)
        self.assertIn("footer", woori_template.revisionProfile.allowedRevisionTargets)
        self.assertIn("chart-visual-mock", woori_template.revisionProfile.forbiddenCssTokens)
        self.assertIsNone(kb_template.revisionProfile)

    def test_rejects_invalid_template_chart_profile(self):
        import json
        import tempfile

        from report_engine.errors import ErrorCode, ReportEngineError
        from report_engine.repository import ReportRepository

        invalid_catalog = {
            "schemaVersion": "poc.etfReport.templates.v1",
            "templateCount": 1,
            "templates": [
                {
                    "templateId": "tpl_invalid",
                    "name": "Invalid",
                    "previewImage": "backend/data/report_template/missing.png",
                    "page": {"size": "A4", "orientation": "portrait"},
                    "chartProfile": {
                        "performance_chart": {
                            "templateImageHasChart": True,
                            "detectedChartType": "pie",
                            "fallbackChartType": "bar",
                        }
                    },
                }
            ],
        }
        with tempfile.TemporaryDirectory() as tmpdir:
            data_dir = Path(tmpdir) / "data"
            data_dir.mkdir()
            (data_dir / "etf_data.json").write_text('{"datasets":[]}', encoding="utf-8")
            (data_dir / "report_templates.json").write_text(json.dumps(invalid_catalog), encoding="utf-8")

            with self.assertRaises(ReportEngineError) as caught:
                ReportRepository(tmpdir).load_template("tpl_invalid")

        self.assertEqual(caught.exception.code, ErrorCode.CONFIG_INVALID)
        self.assertEqual(caught.exception.stage, "repository")

    def test_cross_distributor_dataset_template_combinations_are_allowed(self):
        combinations = [
            ("data_kodex_us_sp500", "tpl_kb_monthly_guidebook"),
            ("data_kodex_us_sp500", "tpl_woori_monthly_report"),
            ("data_kodex_korea_dividend_growth_bond_mixed", "tpl_kb_monthly_guidebook"),
            ("data_kodex_korea_dividend_growth_bond_mixed", "tpl_woori_monthly_report"),
        ]

        for dataset_id, template_id in combinations:
            with self.subTest(dataset_id=dataset_id, template_id=template_id):
                self.assertEqual(self.repository.load_dataset(dataset_id).datasetId, dataset_id)
                self.assertEqual(self.repository.load_template(template_id).templateId, template_id)

    def test_loads_month_component_sources_and_samples(self):
        sources = self.repository.load_component_sources("data_kodex_us_sp500", "2026-03")
        components = self.repository.load_sample_components("data_kodex_us_sp500", "2026-03")

        self.assertEqual([item["componentKey"] for item in sources], self.repository.COMPONENT_KEYS)
        self.assertEqual([item.componentKey for item in components], self.repository.COMPONENT_KEYS)

    def test_missing_identifiers_raise_typed_errors(self):
        from report_engine.errors import ErrorCode, ReportEngineError

        checks = [
            (lambda: self.repository.load_dataset("missing"), ErrorCode.DATASET_NOT_FOUND),
            (lambda: self.repository.load_template("missing"), ErrorCode.TEMPLATE_NOT_FOUND),
            (lambda: self.repository.load_month_snapshot("data_kodex_us_sp500", "2099-01"), ErrorCode.MONTH_NOT_FOUND),
        ]

        for action, expected_code in checks:
            with self.subTest(expected_code=expected_code):
                with self.assertRaises(ReportEngineError) as caught:
                    action()
                self.assertEqual(caught.exception.code, expected_code)


if __name__ == "__main__":
    unittest.main()
