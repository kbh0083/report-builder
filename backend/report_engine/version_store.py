from datetime import datetime
from pathlib import Path

from .errors import ErrorCode, ReportEngineError
from .models import ReportVersion
from .renderer import HtmlRenderer


class VersionStore:
    def __init__(self, output_root: str | Path):
        self.output_root = Path(output_root)

    def create_version(self, job_id: str, version: int, html: str, renderer: HtmlRenderer) -> ReportVersion:
        self._validate_job_id(job_id)
        if not isinstance(version, int) or version < 1:
            raise self._render_failed("Version must be a positive integer")

        version_dir = self.output_root / job_id / f"v{version}"
        html_path = version_dir / "report.html"
        preview_path = version_dir / "preview.png"
        try:
            version_dir.mkdir(parents=True, exist_ok=True)
            html_path.write_text(html, encoding="utf-8")
            renderer.render_html_to_png(html_path, preview_path)
        except ReportEngineError:
            raise
        except Exception as exc:
            raise self._render_failed("Version rendering failed") from exc

        if not preview_path.is_file() or preview_path.stat().st_size <= 0:
            raise self._render_failed("Preview image was not created")

        return ReportVersion(
            jobId=job_id,
            version=version,
            htmlPath=str(html_path),
            previewImagePath=str(preview_path),
            status="verifying",
            createdAt=datetime.now().astimezone().isoformat(timespec="seconds"),
        )

    def _validate_job_id(self, job_id: str) -> None:
        job_path = Path(job_id)
        if job_path.is_absolute() or ".." in job_path.parts or len(job_path.parts) != 1:
            raise self._render_failed(f"Job id must be a single safe path segment: {job_id}")

    @staticmethod
    def _render_failed(detail: str) -> ReportEngineError:
        return ReportEngineError(ErrorCode.RENDER_FAILED, detail, stage="stage4")
