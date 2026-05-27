import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch


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

    def test_llm_settings_default_to_reference_qwen_call_policy(self):
        from report_engine.settings import load_llm_settings

        with tempfile.TemporaryDirectory() as tmpdir:
            env_path = Path(tmpdir) / ".env"
            env_path.write_text(
                "\n".join(
                    [
                        "LLM_MODEL=qwen/qwen3.6-27b",
                        "LLM_BASE_URL=https://api.novita.ai/openai",
                        "LLM_API_KEY=secret-key-123",
                        "LLM_TEMPERATURE=0",
                        "LLM_MAX_TOKENS=4096",
                        "LLM_TIMEOUT_SECONDS=120",
                        "LLM_CHUNK_SIZE_CHARS=12000",
                        "LLM_STAGE_BATCH_SIZE=5",
                    ]
                ),
                encoding="utf-8",
            )

            with patch.dict("os.environ", {}, clear=True):
                settings = load_llm_settings(env_path)

        self.assertEqual(settings.topP, 1.0)
        self.assertEqual(settings.retryAttempts, 3)
        self.assertEqual(settings.parseRetryAttempts, 3)
        self.assertEqual(settings.enableThinking, False)
        self.assertEqual(settings.separateReasoning, True)


if __name__ == "__main__":
    unittest.main()
