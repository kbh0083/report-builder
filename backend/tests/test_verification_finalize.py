import json
import struct
import tempfile
import unittest
import zlib
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

            def create_revision(version, result, next_version_number):
                revision_requests.append((version.version, result.revisionInstruction, next_version_number))
                return _write_version(tmpdir, "job_task8", next_version_number, html="v2 html", preview=b"v2 png")

            loop = Stage5VerificationService().verify_until_passed(
                first_version,
                verification_mode="novita",
                max_iterations=3,
                adapter=adapter,
                create_revision=create_revision,
            )

            self.assertEqual(adapter.checked_versions, [1, 2])
            self.assertEqual(revision_requests, [(1, "Increase chart spacing and preserve footer safe area.", 2)])
            self.assertEqual(loop.passedVersion.version, 2)
            self.assertEqual([attempt.reportVersion.version for attempt in loop.attempts], [1, 2])
            self.assertFalse(loop.attempts[0].result.passed)
            self.assertTrue(loop.attempts[1].result.passed)
            self.assertTrue((Path(first_version.htmlPath).parent / "verification.json").is_file())
            self.assertTrue((Path(loop.passedVersion.htmlPath).parent / "verification.json").is_file())

    def test_novita_revision_loop_returns_best_failed_when_max_iterations_exhausted(self):
        from report_engine.stage5_verification import Stage5VerificationService

        with tempfile.TemporaryDirectory() as tmpdir:
            first_version = _write_version(tmpdir, "job_task8", 1, html="v1 html", preview=b"v1 png")

            loop = Stage5VerificationService().verify_until_passed(
                first_version,
                verification_mode="novita",
                max_iterations=1,
                adapter=FakeAlwaysRevisionVerificationAdapter(),
                create_revision=lambda version, result, next_version_number: _write_version(
                    tmpdir,
                    "job_task8",
                    next_version_number,
                    html="next html",
                    preview=b"next png",
                ),
            )

            self.assertIsNone(loop.passedVersion)
            self.assertTrue(loop.maxIterationsExceeded)
            self.assertEqual(loop.bestFailedVersion.version, 1)
            self.assertEqual([attempt.reportVersion.version for attempt in loop.attempts], [1])

    def test_novita_revision_uses_best_failed_version_when_latest_regresses(self):
        from report_engine.stage5_verification import Stage5VerificationService

        with tempfile.TemporaryDirectory() as tmpdir:
            first_version = _write_version(
                tmpdir,
                "job_woori",
                1,
                html="v1 html",
                preview=_png_bytes(100, 100),
            )
            adapter = FakeRegressionThenPassVerificationAdapter()
            revision_requests = []

            def create_revision(version, result, next_version_number=None):
                version_number = next_version_number if next_version_number is not None else version.version + 1
                revision_requests.append(
                    (
                        version.version,
                        result.revisionInstruction,
                        version_number,
                    )
                )
                if version_number == 2:
                    return _write_version(
                        tmpdir,
                        "job_woori",
                        2,
                        html="v2 html",
                        preview=_png_bytes(100, 180),
                    )
                return _write_version(
                    tmpdir,
                    "job_woori",
                    3,
                    html="v3 html",
                    preview=_png_bytes(100, 110),
                )

            loop = Stage5VerificationService().verify_until_passed(
                first_version,
                verification_mode="novita",
                max_iterations=3,
                adapter=adapter,
                create_revision=create_revision,
            )

            self.assertEqual(adapter.checked_versions, [1, 2, 3])
            self.assertEqual(
                revision_requests,
                [
                    (1, "Patch header, footer, marker, and table style only.", 2),
                    (1, "Patch header, footer, marker, and table style only.", 3),
                ],
            )
            self.assertEqual(loop.passedVersion.version, 3)
            self.assertEqual(loop.bestFailedVersion.version, 1)
            self.assertEqual(loop.bestFailedScore, 10)
            self.assertEqual(
                loop.regressedVersions,
                [
                    {
                        "version": 2,
                        "regressedFromVersion": 1,
                        "score": 25,
                        "bestFailedScore": 10,
                    }
                ],
            )

    def test_revision_profile_dimension_threshold_controls_regression_score(self):
        from report_engine.models import PageSettings, TemplateContext, TemplateRevisionProfile
        from report_engine.stage5_verification import Stage5VerificationService

        with tempfile.TemporaryDirectory() as tmpdir:
            first_version = _write_version(
                tmpdir,
                "job_woori",
                1,
                html="v1 html",
                preview=_png_bytes(100, 100),
            )
            template_context = TemplateContext(
                templateId="tpl_woori_monthly_report",
                previewImage="backend/data/report_template/우리은행_월간_리포트.png",
                page=PageSettings(size="A4", orientation="portrait"),
                revisionProfile=TemplateRevisionProfile(
                    revisionMode="minimal_patch",
                    preserveInitialGrid=True,
                    maxPreviewDimensionDriftRatio=1.0,
                ),
            )

            def create_revision(version, result, next_version_number):
                return _write_version(
                    tmpdir,
                    "job_woori",
                    next_version_number,
                    html="v2 html",
                    preview=_png_bytes(100, 180),
                )

            loop = Stage5VerificationService().verify_until_passed(
                first_version,
                verification_mode="novita",
                max_iterations=3,
                adapter=FakeDimensionDriftVerificationAdapter(),
                create_revision=create_revision,
                template_context=template_context,
            )

            self.assertIsNone(loop.passedVersion)
            self.assertEqual([attempt.score for attempt in loop.attempts], [3, 3])
            self.assertEqual(loop.bestFailedScore, 3)
            self.assertEqual(loop.regressedVersions, [])

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

    def test_finalize_can_use_best_failed_attempt_after_max_iterations(self):
        from report_engine.models import VerificationResult
        from report_engine.stage5_verification import VerificationAttempt
        from report_engine.stage6_finalize import Stage6Finalizer

        with tempfile.TemporaryDirectory() as tmpdir:
            first_version = _write_version(tmpdir, "job_task8", 1, html="v1 best failed html", preview=b"v1 png")
            second_version = _write_version(tmpdir, "job_task8", 2, html="v2 worse html", preview=b"v2 png")
            attempts = [
                VerificationAttempt(
                    reportVersion=first_version,
                    result=VerificationResult(passed=False, issues=[{"severity": "major"}]),
                    verificationPath=str(Path(first_version.htmlPath).parent / "verification.json"),
                    score=3,
                ),
                VerificationAttempt(
                    reportVersion=second_version,
                    result=VerificationResult(passed=False, issues=[{"severity": "critical"}]),
                    verificationPath=str(Path(second_version.htmlPath).parent / "verification.json"),
                    score=10,
                ),
            ]

            final = Stage6Finalizer(tmpdir).finalize(
                "job_task8",
                attempts,
                allow_failed_fallback=True,
            )

            self.assertEqual(final.sourceVersion, 1)
            self.assertEqual(Path(final.reportHtmlPath).read_text(encoding="utf-8"), "v1 best failed html")
            self.assertEqual(Path(final.previewImagePath).read_bytes(), b"v1 png")


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


class FakeRegressionThenPassVerificationAdapter:
    def __init__(self):
        self.checked_versions = []

    def verify_report_version(self, report_version, *, template_context=None):
        self.checked_versions.append(report_version.version)
        if report_version.version == 1:
            return {
                "passed": False,
                "issues": [
                    {"type": "template_mismatch", "severity": "major"},
                    {"type": "template_mismatch", "severity": "major"},
                    {"type": "template_mismatch", "severity": "major"},
                    {"type": "template_mismatch", "severity": "minor"},
                ],
                "revisionInstruction": "Patch header, footer, marker, and table style only.",
            }
        if report_version.version == 2:
            return {
                "passed": False,
                "issues": [
                    {"type": "template_mismatch", "severity": "critical"},
                    {"type": "template_mismatch", "severity": "major"},
                    {"type": "template_mismatch", "severity": "major"},
                ],
                "revisionInstruction": "Rewrite the whole main content grid.",
            }
        return {"passed": True, "issues": []}


class FakeDimensionDriftVerificationAdapter:
    def verify_report_version(self, report_version, *, template_context=None):
        if report_version.version == 1:
            return {
                "passed": False,
                "issues": [
                    {
                        "type": "template_mismatch",
                        "severity": "major",
                        "description": "Header differs from template.",
                    }
                ],
                "revisionInstruction": "Patch only the header.",
            }
        return {
            "passed": False,
            "issues": [
                {
                    "type": "template_mismatch",
                    "severity": "major",
                    "description": "Footer differs from template.",
                }
            ],
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


def _png_bytes(width, height):
    def chunk(kind, data):
        payload = kind + data
        return struct.pack(">I", len(data)) + payload + struct.pack(">I", zlib.crc32(payload) & 0xFFFFFFFF)

    raw = b"".join(b"\x00" + b"\xff\xff\xff" * width for _ in range(height))
    return (
        b"\x89PNG\r\n\x1a\n"
        + chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0))
        + chunk(b"IDAT", zlib.compress(raw))
        + chunk(b"IEND", b"")
    )


if __name__ == "__main__":
    unittest.main()
