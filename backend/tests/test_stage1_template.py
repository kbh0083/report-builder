import unittest
from pathlib import Path


BACKEND_ROOT = Path(__file__).resolve().parents[1]
WORKSPACE_ROOT = BACKEND_ROOT.parent


class Stage1TemplateTests(unittest.TestCase):
    def setUp(self):
        from report_engine.repository import ReportRepository
        from report_engine.stage1_template import Stage1TemplateService

        self.service = Stage1TemplateService(ReportRepository(WORKSPACE_ROOT))

    def test_validates_known_templates(self):
        for template_id in ["tpl_kb_monthly_guidebook", "tpl_woori_monthly_report"]:
            with self.subTest(template_id=template_id):
                context = self.service.load_template_context(template_id)
                self.assertEqual(context.templateId, template_id)
                self.assertFalse(hasattr(context, "sourceHtml"))
                self.assertTrue(context.previewImage.startswith("backend/data/report_template/"))
                self.assertEqual(context.page.size, "A4")
                self.assertEqual(context.page.orientation, "portrait")

    def test_rejects_missing_preview_path(self):
        from report_engine.errors import ErrorCode, ReportEngineError
        from report_engine.models import PageSettings, TemplateContext

        context = TemplateContext(
            templateId="broken",
            previewImage="backend/data/report_template/missing.png",
            page=PageSettings(size="A4", orientation="portrait"),
        )

        with self.assertRaises(ReportEngineError) as caught:
            self.service.validate_template_context(context)
        self.assertEqual(caught.exception.code, ErrorCode.TEMPLATE_NOT_FOUND)


if __name__ == "__main__":
    unittest.main()
