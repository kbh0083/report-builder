import shutil
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from .errors import ErrorCode, ReportEngineError
from .stage5_verification import VerificationAttempt


@dataclass(frozen=True)
class FinalReport:
    jobId: str
    sourceVersion: int
    reportHtmlPath: str
    previewImagePath: str
    finalizedAt: str


class Stage6Finalizer:
    def __init__(self, output_root: str | Path):
        self.output_root = Path(output_root)

    def finalize(self, job_id: str, attempts: list[VerificationAttempt]) -> FinalReport:
        self._validate_job_id(job_id)
        passed_attempt = self._latest_passed_attempt(attempts)
        if passed_attempt is None:
            raise ReportEngineError(
                ErrorCode.NO_PASSED_VERSION,
                "No report version passed verification",
                stage="stage6",
            )

        final_dir = self.output_root / job_id / "final"
        final_dir.mkdir(parents=True, exist_ok=True)
        report_html_path = final_dir / "report.html"
        preview_path = final_dir / "preview.png"

        source_report = Path(passed_attempt.reportVersion.htmlPath)
        source_preview = Path(passed_attempt.reportVersion.previewImagePath)
        self._copy_required_file(source_report, report_html_path)
        self._copy_required_file(source_preview, preview_path)

        return FinalReport(
            jobId=job_id,
            sourceVersion=passed_attempt.reportVersion.version,
            reportHtmlPath=str(report_html_path),
            previewImagePath=str(preview_path),
            finalizedAt=datetime.now().astimezone().isoformat(timespec="seconds"),
        )

    def _latest_passed_attempt(self, attempts: list[VerificationAttempt]) -> VerificationAttempt | None:
        for attempt in reversed(attempts):
            if attempt.result.passed:
                return attempt
        return None

    def _copy_required_file(self, source: Path, destination: Path) -> None:
        if not source.is_file() or source.stat().st_size <= 0:
            raise ReportEngineError(
                ErrorCode.CONFIG_INVALID,
                f"Final source asset is missing: {source}",
                stage="stage6",
            )
        shutil.copy2(source, destination)
        if not destination.is_file() or destination.stat().st_size <= 0:
            raise ReportEngineError(
                ErrorCode.CONFIG_INVALID,
                f"Final asset was not created: {destination}",
                stage="stage6",
            )

    def _validate_job_id(self, job_id: str) -> None:
        job_path = Path(job_id)
        if job_path.is_absolute() or ".." in job_path.parts or len(job_path.parts) != 1:
            raise ReportEngineError(
                ErrorCode.CONFIG_INVALID,
                f"Job id must be a single safe path segment: {job_id}",
                stage="stage6",
            )
