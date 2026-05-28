from pathlib import Path
from typing import Any, Protocol

from .errors import ErrorCode, ReportEngineError


class HtmlRenderer(Protocol):
    def render_html_to_png(self, html_path: Path, preview_path: Path) -> Path:
        """Render an HTML file into a PNG preview."""


class PlaceholderRenderer:
    """Write a tiny PNG so CLI smoke tests can exercise Stage 4 without a browser."""

    _PNG_BYTES = (
        b"\x89PNG\r\n\x1a\n"
        b"\x00\x00\x00\rIHDR"
        b"\x00\x00\x00\x01\x00\x00\x00\x01\x08\x06\x00\x00\x00"
        b"\x1f\x15\xc4\x89"
        b"\x00\x00\x00\rIDATx\x9cc\xf8\xff\xff?\x00\x05\xfe\x02\xfe"
        b"\xdc\xccY\xe7"
        b"\x00\x00\x00\x00IEND\xaeB`\x82"
    )

    def render_html_to_png(self, html_path: Path, preview_path: Path) -> Path:
        preview_path = Path(preview_path)
        preview_path.parent.mkdir(parents=True, exist_ok=True)
        preview_path.write_bytes(self._PNG_BYTES)
        return preview_path


class PlaywrightRenderer:
    def __init__(
        self,
        sync_playwright_factory: Any | None = None,
        viewport_width: int = 794,
        viewport_height: int = 1123,
        device_scale_factor: int = 2,
    ):
        self.sync_playwright_factory = sync_playwright_factory
        self.viewport_width = viewport_width
        self.viewport_height = viewport_height
        self.device_scale_factor = device_scale_factor

    def render_html_to_png(self, html_path: Path, preview_path: Path) -> Path:
        html_path = Path(html_path)
        preview_path = Path(preview_path)
        preview_path.parent.mkdir(parents=True, exist_ok=True)
        try:
            factory = self.sync_playwright_factory or self._load_sync_playwright()
            with factory() as playwright:
                browser = playwright.chromium.launch(headless=True, chromium_sandbox=False)
                try:
                    context = browser.new_context(
                        viewport={"width": self.viewport_width, "height": self.viewport_height},
                        device_scale_factor=self.device_scale_factor,
                    )
                    page = context.new_page()
                    page.goto(html_path.resolve().as_uri(), wait_until="networkidle")
                    page.screenshot(path=str(preview_path), full_page=True)
                finally:
                    browser.close()
        except ReportEngineError:
            raise
        except Exception as exc:
            raise self._render_failed("Playwright preview rendering failed") from exc

        if not preview_path.is_file() or preview_path.stat().st_size <= 0:
            raise self._render_failed("Preview image was not created")
        return preview_path

    @staticmethod
    def _load_sync_playwright():
        try:
            from playwright.sync_api import sync_playwright
        except ImportError as exc:
            raise PlaywrightRenderer._render_failed("Playwright is not installed") from exc
        return sync_playwright

    @staticmethod
    def _render_failed(detail: str) -> ReportEngineError:
        return ReportEngineError(ErrorCode.RENDER_FAILED, detail, stage="stage4")
