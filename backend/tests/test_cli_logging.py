import json
import shutil
import subprocess
import sys
import unittest
from pathlib import Path

from report_engine.logging_flow import _build_report_draft_html
from report_engine.models import Stage2Component


BACKEND_ROOT = Path(__file__).resolve().parents[1]
EXPECTED_STAGE_FILES = [
    "00_request/request.json",
    "01_template/template_context.json",
    "02_components/component_sources.json",
    "02_components/components.json",
    "03_layout/prompt_input.json",
    "03_layout/report_draft.html",
    "04_render/render_result.json",
    "05_verification/verification.json",
    "06_final/final_result.json",
]
EXPECTED_COMPONENT_HTML = [
    "performance_chart.html",
    "performance_summary.html",
    "top_holdings.html",
    "review.html",
    "outlook.html",
]


class CliLoggingTests(unittest.TestCase):
    def test_run_writes_stage_logs_and_component_html_files(self):
        result = subprocess.run(
            [
                sys.executable,
                "-m",
                "report_engine",
                "run",
                "--dataset-id",
                "data_kodex_us_sp500",
                "--template-id",
                "tpl_kb_monthly_guidebook",
                "--month-id",
                "2026-03",
                "--component-mode",
                "sample",
                "--verification-mode",
                "manual-pass",
            ],
            cwd=BACKEND_ROOT,
            check=False,
            capture_output=True,
            text=True,
        )

        self.assertEqual(result.returncode, 0, result.stderr)
        event = json.loads(result.stdout.strip().splitlines()[-1])
        self.assertEqual(event["event"], "job.logged")
        job_dir = Path(event["logPath"])
        self.addCleanup(lambda: shutil.rmtree(job_dir, ignore_errors=True))

        self.assertTrue(job_dir.is_dir())
        for relative_path in EXPECTED_STAGE_FILES:
            self.assertTrue((job_dir / relative_path).is_file(), relative_path)

        html_dir = job_dir / "02_components" / "html"
        for filename in EXPECTED_COMPONENT_HTML:
            path = html_dir / filename
            self.assertTrue(path.is_file(), filename)
            self.assertIn("data-component-id", path.read_text(encoding="utf-8"))

        report_draft = (job_dir / "03_layout" / "report_draft.html").read_text(encoding="utf-8")
        self.assertIn("<!doctype html>", report_draft)
        self.assertIn("comp_data_kodex_us_sp500_2026_03_performance_chart", report_draft)

    def test_run_logs_do_not_include_llm_api_key_value(self):
        secret_value = "test-secret-value-for-log-redaction"
        result = subprocess.run(
            [
                sys.executable,
                "-m",
                "report_engine",
                "run",
                "--dataset-id",
                "data_kodex_us_sp500",
                "--template-id",
                "tpl_kb_monthly_guidebook",
                "--month-id",
                "2026-03",
                "--component-mode",
                "sample",
                "--verification-mode",
                "manual-pass",
            ],
            cwd=BACKEND_ROOT,
            check=False,
            capture_output=True,
            text=True,
            env={**__import__("os").environ, "LLM_API_KEY": secret_value},
        )

        self.assertEqual(result.returncode, 0, result.stderr)
        event = json.loads(result.stdout.strip().splitlines()[-1])
        job_dir = Path(event["logPath"])
        self.addCleanup(lambda: shutil.rmtree(job_dir, ignore_errors=True))

        combined = "\n".join(
            path.read_text(encoding="utf-8")
            for path in job_dir.rglob("*")
            if path.is_file()
        )
        self.assertNotIn(secret_value, combined)
        self.assertIn("<redacted>", combined)

    def test_report_draft_escapes_product_name_metadata(self):
        component = Stage2Component(
            componentId="comp_x",
            componentKey="review",
            datasetId="data_x",
            monthId="2026-03",
            dataSourceId="ds_x",
            renderType="list",
            html='<section data-component-id="comp_x"><p>OK</p></section>',
            chartSpec=None,
            styled=False,
        )

        html = _build_report_draft_html('Kodex "S&P<500>"', [component])

        self.assertIn("<title>Kodex &quot;S&amp;P&lt;500&gt;&quot;</title>", html)
        self.assertIn('data-report-product="Kodex &quot;S&amp;P&lt;500&gt;&quot;"', html)
        self.assertIn('<section data-component-id="comp_x"><p>OK</p></section>', html)


if __name__ == "__main__":
    unittest.main()
