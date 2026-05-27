import json
import tempfile
import unittest
from pathlib import Path


class ArtifactLoggerTests(unittest.TestCase):
    def test_writes_json_and_html_under_job_directory(self):
        from report_engine.artifact_logger import ArtifactLogger

        with tempfile.TemporaryDirectory() as tmpdir:
            logger = ArtifactLogger(Path(tmpdir), "job_test_001")

            json_path = logger.write_json("00_request/request.json", {"message": "안녕하세요", "count": 1})
            html_path = logger.write_html("03_layout/report_draft.html", "<html><body>리포트</body></html>")

            self.assertEqual(json_path, Path(tmpdir) / "job_test_001" / "00_request" / "request.json")
            self.assertEqual(html_path, Path(tmpdir) / "job_test_001" / "03_layout" / "report_draft.html")
            self.assertEqual(json.loads(json_path.read_text(encoding="utf-8"))["message"], "안녕하세요")
            self.assertIn('\n  "message": "안녕하세요"', json_path.read_text(encoding="utf-8"))
            self.assertEqual(html_path.read_text(encoding="utf-8"), "<html><body>리포트</body></html>")

    def test_rejects_job_id_path_traversal(self):
        from report_engine.artifact_logger import ArtifactLogger

        with tempfile.TemporaryDirectory() as tmpdir:
            with self.assertRaises(ValueError):
                ArtifactLogger(Path(tmpdir), "../outside")
            with self.assertRaises(ValueError):
                ArtifactLogger(Path(tmpdir), "nested/job")
            with self.assertRaises(ValueError):
                ArtifactLogger(Path(tmpdir), "/tmp/job")

    def test_redacts_secret_values_in_json_and_html(self):
        from report_engine.artifact_logger import ArtifactLogger

        with tempfile.TemporaryDirectory() as tmpdir:
            logger = ArtifactLogger(Path(tmpdir), "job_secret", secrets=["real-secret-value"])

            json_path = logger.write_json(
                "00_request/request.json",
                {
                    "LLM_API_KEY": "real-secret-value",
                    "message": "token real-secret-value",
                    "nested": {"apiKey": "real-secret-value"},
                },
            )
            html_path = logger.write_html("03_layout/report_draft.html", "<p>real-secret-value</p>")

            for path in [json_path, html_path]:
                text = path.read_text(encoding="utf-8")
                self.assertNotIn("real-secret-value", text)
                self.assertIn("<redacted>", text)

    def test_redacts_common_camel_case_credential_keys(self):
        from report_engine.artifact_logger import ArtifactLogger

        with tempfile.TemporaryDirectory() as tmpdir:
            logger = ArtifactLogger(Path(tmpdir), "job_secret_keys")

            json_path = logger.write_json(
                "03_layout/prompt_input.json",
                {
                    "clientSecret": "client-secret-value",
                    "accessToken": "access-token-value",
                    "privateKey": "private-key-value",
                    "tokenUsage": {"input": 100, "output": 50},
                },
            )
            payload = json.loads(json_path.read_text(encoding="utf-8"))

            self.assertEqual(payload["clientSecret"], "<redacted>")
            self.assertEqual(payload["accessToken"], "<redacted>")
            self.assertEqual(payload["privateKey"], "<redacted>")
            self.assertEqual(payload["tokenUsage"], {"input": 100, "output": 50})


if __name__ == "__main__":
    unittest.main()
