import subprocess
import sys
import unittest
from pathlib import Path


BACKEND_ROOT = Path(__file__).resolve().parents[1]


class CliAndSettingsTests(unittest.TestCase):
    def test_module_help_runs(self):
        result = subprocess.run(
            [sys.executable, "-m", "report_engine", "--help"],
            cwd=BACKEND_ROOT,
            check=False,
            capture_output=True,
            text=True,
        )

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("run", result.stdout)
        self.assertIn("--dataset-id", result.stdout)
        self.assertIn("--template-id", result.stdout)

    def test_report_job_request_accepts_expected_modes(self):
        from report_engine.models import ReportJobRequest

        request = ReportJobRequest(
            datasetId="data_kodex_us_sp500",
            templateId="tpl_kb_monthly_guidebook",
            monthId="2026-03",
            componentMode="sample",
            layoutMode="novita",
            verificationMode="manual-pass",
            maxIterations=3,
            outputDir="runs",
        )

        self.assertEqual(request.datasetId, "data_kodex_us_sp500")
        self.assertEqual(request.componentMode, "sample")

    def test_redact_secrets_masks_llm_api_key_value(self):
        from report_engine.settings import redact_secret_values

        text = "api key value secret-key-123 and token secret-key-123"
        redacted = redact_secret_values(text, ["secret-key-123"])

        self.assertNotIn("secret-key-123", redacted)
        self.assertEqual(redacted.count("<redacted>"), 2)


if __name__ == "__main__":
    unittest.main()
