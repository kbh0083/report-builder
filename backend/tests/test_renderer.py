import os
import tempfile
import unittest
from importlib.util import find_spec
from pathlib import Path


class PlaywrightRendererTests(unittest.TestCase):
    def test_render_html_to_png_uses_file_url_and_writes_preview(self):
        from report_engine.renderer import PlaywrightRenderer

        fake_playwright = FakePlaywright(write_preview=True)
        with tempfile.TemporaryDirectory() as tmpdir:
            html_path = Path(tmpdir) / "report.html"
            preview_path = Path(tmpdir) / "preview.png"
            html_path.write_text("<!doctype html><html><body>ok</body></html>", encoding="utf-8")

            result = PlaywrightRenderer(sync_playwright_factory=lambda: fake_playwright).render_html_to_png(
                html_path,
                preview_path,
            )

            self.assertEqual(result, preview_path)
            self.assertEqual(preview_path.read_bytes(), b"png")
            self.assertEqual(fake_playwright.browser.launch_kwargs["headless"], True)
            self.assertEqual(fake_playwright.browser.launch_kwargs["chromium_sandbox"], False)
            self.assertEqual(fake_playwright.browser.context_kwargs["viewport"], {"width": 794, "height": 1123})
            self.assertEqual(fake_playwright.browser.context_kwargs["device_scale_factor"], 2)
            self.assertEqual(fake_playwright.page.goto_url, html_path.resolve().as_uri())
            self.assertEqual(fake_playwright.page.goto_kwargs["wait_until"], "networkidle")
            self.assertEqual(fake_playwright.page.screenshot_kwargs["path"], str(preview_path))
            self.assertEqual(fake_playwright.page.screenshot_kwargs["full_page"], True)
            self.assertTrue(fake_playwright.browser.closed)

    def test_render_html_to_png_converts_playwright_failure_to_render_failed(self):
        from report_engine.errors import ErrorCode, ReportEngineError
        from report_engine.renderer import PlaywrightRenderer

        fake_playwright = FakePlaywright(write_preview=False, fail_screenshot=True)
        with tempfile.TemporaryDirectory() as tmpdir:
            html_path = Path(tmpdir) / "report.html"
            preview_path = Path(tmpdir) / "preview.png"
            html_path.write_text("<!doctype html><html><body>ok</body></html>", encoding="utf-8")

            with self.assertRaises(ReportEngineError) as caught:
                PlaywrightRenderer(sync_playwright_factory=lambda: fake_playwright).render_html_to_png(
                    html_path,
                    preview_path,
                )

        self.assertEqual(caught.exception.code, ErrorCode.RENDER_FAILED)
        self.assertEqual(caught.exception.stage, "stage4")

    def test_render_html_to_png_fails_when_preview_is_missing(self):
        from report_engine.errors import ErrorCode, ReportEngineError
        from report_engine.renderer import PlaywrightRenderer

        fake_playwright = FakePlaywright(write_preview=False)
        with tempfile.TemporaryDirectory() as tmpdir:
            html_path = Path(tmpdir) / "report.html"
            preview_path = Path(tmpdir) / "preview.png"
            html_path.write_text("<!doctype html><html><body>ok</body></html>", encoding="utf-8")

            with self.assertRaises(ReportEngineError) as caught:
                PlaywrightRenderer(sync_playwright_factory=lambda: fake_playwright).render_html_to_png(
                    html_path,
                    preview_path,
                )

        self.assertEqual(caught.exception.code, ErrorCode.RENDER_FAILED)
        self.assertEqual(caught.exception.stage, "stage4")

    @unittest.skipUnless(os.environ.get("RUN_PLAYWRIGHT_RENDERER") == "1", "Playwright renderer integration is opt-in")
    def test_render_html_to_png_with_real_playwright(self):
        if find_spec("playwright") is None:
            self.skipTest("playwright is not installed in this Python environment")
        from report_engine.renderer import PlaywrightRenderer

        with tempfile.TemporaryDirectory() as tmpdir:
            html_path = Path(tmpdir) / "report.html"
            preview_path = Path(tmpdir) / "preview.png"
            html_path.write_text("<!doctype html><html><body><h1>ok</h1></body></html>", encoding="utf-8")

            PlaywrightRenderer().render_html_to_png(html_path, preview_path)

            self.assertTrue(preview_path.is_file())
            self.assertGreater(preview_path.stat().st_size, 0)


class FakePlaywright:
    def __init__(self, write_preview, fail_screenshot=False):
        self.browser = FakeBrowser(write_preview=write_preview, fail_screenshot=fail_screenshot)
        self.chromium = FakeChromium(self.browser)
        self.page = self.browser.page

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return None


class FakeChromium:
    def __init__(self, browser):
        self.browser = browser

    def launch(self, **kwargs):
        self.browser.launch_kwargs = kwargs
        return self.browser


class FakeBrowser:
    def __init__(self, write_preview, fail_screenshot):
        self.page = FakePage(write_preview=write_preview, fail_screenshot=fail_screenshot)
        self.launch_kwargs = None
        self.context_kwargs = None
        self.closed = False

    def new_context(self, **kwargs):
        self.context_kwargs = kwargs
        return FakeContext(self.page)

    def close(self):
        self.closed = True


class FakeContext:
    def __init__(self, page):
        self.page = page

    def new_page(self):
        return self.page


class FakePage:
    def __init__(self, write_preview, fail_screenshot):
        self.write_preview = write_preview
        self.fail_screenshot = fail_screenshot
        self.goto_url = None
        self.goto_kwargs = None
        self.screenshot_kwargs = None

    def goto(self, url, **kwargs):
        self.goto_url = url
        self.goto_kwargs = kwargs

    def screenshot(self, **kwargs):
        self.screenshot_kwargs = kwargs
        if self.fail_screenshot:
            raise RuntimeError("synthetic screenshot failure")
        if self.write_preview:
            Path(kwargs["path"]).write_bytes(b"png")


if __name__ == "__main__":
    unittest.main()
