import tempfile
import unittest
from pathlib import Path


class VersionStoreTests(unittest.TestCase):
    def test_create_version_writes_report_preview_and_metadata(self):
        from report_engine.version_store import VersionStore

        with tempfile.TemporaryDirectory() as tmpdir:
            version = VersionStore(tmpdir).create_version(
                job_id="job_20260527_001",
                version=1,
                html="<!doctype html><html><body>ok</body></html>",
                renderer=FakeRenderer(write_preview=True),
            )
            root = Path(tmpdir)

            self.assertEqual(version.jobId, "job_20260527_001")
            self.assertEqual(version.version, 1)
            self.assertEqual(version.status, "verifying")
            self.assertTrue(version.createdAt)
            self.assertEqual(Path(version.htmlPath), root / "job_20260527_001" / "v1" / "report.html")
            self.assertEqual(Path(version.previewImagePath), root / "job_20260527_001" / "v1" / "preview.png")
            self.assertEqual(Path(version.htmlPath).read_text(encoding="utf-8"), "<!doctype html><html><body>ok</body></html>")
            self.assertEqual(Path(version.previewImagePath).read_bytes(), b"png")

    def test_create_version_fails_when_renderer_does_not_create_preview(self):
        from report_engine.errors import ErrorCode, ReportEngineError
        from report_engine.version_store import VersionStore

        with tempfile.TemporaryDirectory() as tmpdir:
            with self.assertRaises(ReportEngineError) as caught:
                VersionStore(tmpdir).create_version(
                    job_id="job_20260527_001",
                    version=1,
                    html="<!doctype html><html><body>ok</body></html>",
                    renderer=FakeRenderer(write_preview=False),
                )

        self.assertEqual(caught.exception.code, ErrorCode.RENDER_FAILED)
        self.assertEqual(caught.exception.stage, "stage4")

    def test_create_version_preserves_injected_chart_svg_in_report_html(self):
        from report_engine.version_store import VersionStore

        chart_html = (
            '<!doctype html><html><body><svg data-chart-rendered="performance_chart">'
            "<title>ETF performance chart</title></svg></body></html>"
        )

        with tempfile.TemporaryDirectory() as tmpdir:
            version = VersionStore(tmpdir).create_version(
                job_id="job_20260527_001",
                version=1,
                html=chart_html,
                renderer=FakeRenderer(write_preview=True),
            )

            report_html = Path(version.htmlPath).read_text(encoding="utf-8")
            self.assertIn('data-chart-rendered="performance_chart"', report_html)
            self.assertNotIn("data-chart-placeholder", report_html)

    def test_create_version_rejects_unsafe_job_id_and_invalid_version(self):
        from report_engine.errors import ErrorCode, ReportEngineError
        from report_engine.version_store import VersionStore

        with tempfile.TemporaryDirectory() as tmpdir:
            store = VersionStore(tmpdir)
            for job_id, version in [
                ("../bad", 1),
                (str(Path(tmpdir) / "absolute"), 1),
                ("job_20260527_001", 0),
            ]:
                with self.subTest(job_id=job_id, version=version):
                    with self.assertRaises(ReportEngineError) as caught:
                        store.create_version(
                            job_id=job_id,
                            version=version,
                            html="<!doctype html><html><body>ok</body></html>",
                            renderer=FakeRenderer(write_preview=True),
                        )
                    self.assertEqual(caught.exception.code, ErrorCode.RENDER_FAILED)
                    self.assertEqual(caught.exception.stage, "stage4")


class FakeRenderer:
    def __init__(self, write_preview):
        self.write_preview = write_preview

    def render_html_to_png(self, html_path, preview_path):
        if self.write_preview:
            preview_path.write_bytes(b"png")
        return preview_path


if __name__ == "__main__":
    unittest.main()
