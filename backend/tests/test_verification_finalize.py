import json
import tempfile
import unittest
from pathlib import Path


class VerificationFinalizeTests(unittest.TestCase):
    def test_manual_pass_writes_verification_json_and_finalizes_report_assets(self):
        from report_engine.stage5_verification import Stage5VerificationService
        from report_engine.stage6_finalize import Stage6Finalizer

        with tempfile.TemporaryDirectory() as tmpdir:
            version = _write_version(tmpdir, "job_task8", 1, html="v1 html", preview=b"v1 png")

            loop = Stage5VerificationService().verify_until_passed(
                version,
                verification_mode="manual-pass",
                max_iterations=3,
            )
            final = Stage6Finalizer(tmpdir).finalize("job_task8", loop.attempts)

            verification_path = Path(version.htmlPath).parent / "verification.json"
            verification = json.loads(verification_path.read_text(encoding="utf-8"))

            self.assertEqual(loop.passedVersion, version)
            self.assertEqual(len(loop.attempts), 1)
            self.assertTrue(loop.attempts[0].result.passed)
            self.assertEqual(loop.attempts[0].verificationPath, str(verification_path))
            self.assertEqual(verification["mode"], "manual-pass")
            self.assertTrue(verification["passed"])
            self.assertEqual(verification["issues"], [])
            self.assertEqual(verification["version"], 1)

            self.assertEqual(final.jobId, "job_task8")
            self.assertEqual(final.sourceVersion, 1)
            self.assertEqual(Path(final.reportHtmlPath), Path(tmpdir) / "job_task8" / "final" / "report.html")
            self.assertEqual(Path(final.previewImagePath), Path(tmpdir) / "job_task8" / "final" / "preview.png")
            self.assertEqual(Path(final.reportHtmlPath).read_text(encoding="utf-8"), "v1 html")
            self.assertEqual(Path(final.previewImagePath).read_bytes(), b"v1 png")
            self.assertTrue(final.finalizedAt)

    def test_novita_fake_verification_can_request_revision_and_pass_next_version(self):
        from report_engine.stage5_verification import Stage5VerificationService

        with tempfile.TemporaryDirectory() as tmpdir:
            first_version = _write_version(tmpdir, "job_task8", 1, html="v1 html", preview=b"v1 png")
            adapter = FakeRevisionVerificationAdapter()
            revision_requests = []

            def create_revision(version, result):
                revision_requests.append((version.version, result.revisionInstruction))
                return _write_version(tmpdir, "job_task8", 2, html="v2 html", preview=b"v2 png")

            loop = Stage5VerificationService().verify_until_passed(
                first_version,
                verification_mode="novita",
                max_iterations=3,
                adapter=adapter,
                create_revision=create_revision,
            )

            self.assertEqual(adapter.checked_versions, [1, 2])
            self.assertEqual(revision_requests, [(1, "Increase chart spacing and preserve footer safe area.")])
            self.assertEqual(loop.passedVersion.version, 2)
            self.assertEqual([attempt.reportVersion.version for attempt in loop.attempts], [1, 2])
            self.assertFalse(loop.attempts[0].result.passed)
            self.assertTrue(loop.attempts[1].result.passed)
            self.assertTrue((Path(first_version.htmlPath).parent / "verification.json").is_file())
            self.assertTrue((Path(loop.passedVersion.htmlPath).parent / "verification.json").is_file())

    def test_novita_revision_loop_stops_at_max_iterations(self):
        from report_engine.errors import ErrorCode, ReportEngineError
        from report_engine.stage5_verification import Stage5VerificationService

        with tempfile.TemporaryDirectory() as tmpdir:
            first_version = _write_version(tmpdir, "job_task8", 1, html="v1 html", preview=b"v1 png")

            with self.assertRaises(ReportEngineError) as caught:
                Stage5VerificationService().verify_until_passed(
                    first_version,
                    verification_mode="novita",
                    max_iterations=1,
                    adapter=FakeAlwaysRevisionVerificationAdapter(),
                    create_revision=lambda version, result: _write_version(
                        tmpdir,
                        "job_task8",
                        version.version + 1,
                        html="next html",
                        preview=b"next png",
                    ),
                )

            self.assertEqual(caught.exception.code, ErrorCode.VERIFICATION_MAX_ITERATIONS_EXCEEDED)
            self.assertEqual(caught.exception.stage, "stage5")

    def test_finalize_fails_when_no_version_passed_verification(self):
        from report_engine.errors import ErrorCode, ReportEngineError
        from report_engine.models import VerificationResult
        from report_engine.stage5_verification import VerificationAttempt
        from report_engine.stage6_finalize import Stage6Finalizer

        with tempfile.TemporaryDirectory() as tmpdir:
            version = _write_version(tmpdir, "job_task8", 1, html="v1 html", preview=b"v1 png")
            attempt = VerificationAttempt(
                reportVersion=version,
                result=VerificationResult(passed=False, issues=[{"code": "layout_overlap"}]),
                verificationPath=str(Path(version.htmlPath).parent / "verification.json"),
            )

            with self.assertRaises(ReportEngineError) as caught:
                Stage6Finalizer(tmpdir).finalize("job_task8", [attempt])

            self.assertEqual(caught.exception.code, ErrorCode.NO_PASSED_VERSION)
            self.assertEqual(caught.exception.stage, "stage6")


class FakeRevisionVerificationAdapter:
    def __init__(self):
        self.checked_versions = []

    def verify_report_version(self, report_version, *, template_context=None):
        self.checked_versions.append(report_version.version)
        if report_version.version == 1:
            return {
                "passed": False,
                "issues": [{"code": "chart_spacing", "severity": "major"}],
                "revisionInstruction": "Increase chart spacing and preserve footer safe area.",
            }
        return {"passed": True, "issues": []}


class FakeAlwaysRevisionVerificationAdapter:
    def verify_report_version(self, report_version, *, template_context=None):
        return {
            "passed": False,
            "issues": [{"code": "still_wrong"}],
            "revisionInstruction": "Try again.",
        }


def _write_version(tmpdir, job_id, version, html, preview):
    from report_engine.models import ReportVersion

    version_dir = Path(tmpdir) / job_id / f"v{version}"
    version_dir.mkdir(parents=True, exist_ok=True)
    html_path = version_dir / "report.html"
    preview_path = version_dir / "preview.png"
    html_path.write_text(html, encoding="utf-8")
    preview_path.write_bytes(preview)
    return ReportVersion(
        jobId=job_id,
        version=version,
        htmlPath=str(html_path),
        previewImagePath=str(preview_path),
        status="verifying",
        createdAt="2026-05-28T00:00:00+09:00",
    )


if __name__ == "__main__":
    unittest.main()
