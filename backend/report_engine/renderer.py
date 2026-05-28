import binascii
import struct
import zlib
from pathlib import Path
from typing import Any, Protocol

from .errors import ErrorCode, ReportEngineError


class HtmlRenderer(Protocol):
    def render_html_to_png(self, html_path: Path, preview_path: Path) -> Path:
        """Render an HTML file into a PNG preview."""


class PlaceholderRenderer:
    """Write a displayable browser-free preview placeholder for CLI smoke tests."""

    width = 794
    height = 1123
    _png_bytes: bytes | None = None

    def render_html_to_png(self, html_path: Path, preview_path: Path) -> Path:
        preview_path = Path(preview_path)
        preview_path.parent.mkdir(parents=True, exist_ok=True)
        preview_path.write_bytes(self._placeholder_png())
        return preview_path

    @classmethod
    def _placeholder_png(cls) -> bytes:
        if cls._png_bytes is None:
            cls._png_bytes = _build_placeholder_png(cls.width, cls.height)
        return cls._png_bytes


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


def _build_placeholder_png(width: int, height: int) -> bytes:
    raw = bytearray()
    for y in range(height):
        raw.append(0)
        for x in range(width):
            if x < 8 or y < 8 or x >= width - 8 or y >= height - 8:
                raw.extend((86, 96, 111, 255))
            elif 32 <= x < width - 32 and 32 <= y < 96:
                raw.extend((31, 94, 255, 255))
            else:
                raw.extend((245, 247, 250, 255))
    return (
        b"\x89PNG\r\n\x1a\n"
        + _png_chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, 8, 6, 0, 0, 0))
        + _png_chunk(b"IDAT", zlib.compress(bytes(raw), level=9))
        + _png_chunk(b"IEND", b"")
    )


def _png_chunk(kind: bytes, payload: bytes) -> bytes:
    checksum = binascii.crc32(kind + payload) & 0xFFFFFFFF
    return struct.pack(">I", len(payload)) + kind + payload + struct.pack(">I", checksum)
