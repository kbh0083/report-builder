import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from types import SimpleNamespace
from pathlib import Path
from threading import Lock
from time import sleep
from unittest.mock import patch

from report_engine.logging_flow import _build_report_draft_html
from report_engine.models import Stage2Component


BACKEND_ROOT = Path(__file__).resolve().parents[1]
EXPECTED_STAGE_FILES = [
    "00_request/request.json",
    "01_template/template_context.json",
    "02_components/component_sources.json",
    "02_components/components.json",
    "03_layout/prompt_input.json",
    "03_layout/report_draft.html",
    "04_render/render_result.json",
    "05_verification/verification.json",
    "06_final/final_result.json",
]
EXPECTED_COMPONENT_HTML = [
    "performance_chart.html",
    "performance_summary.html",
    "top_holdings.html",
    "review.html",
    "outlook.html",
]


class CliLoggingTests(unittest.TestCase):
    def test_run_writes_stage_logs_and_component_html_files(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            result = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "report_engine",
                    "run",
                    "--dataset-id",
                    "data_kodex_us_sp500",
                    "--template-id",
                    "tpl_kb_monthly_guidebook",
                    "--month-id",
                    "2026-03",
                    "--component-mode",
                    "sample",
                    "--verification-mode",
                    "manual-pass",
                    "--renderer-mode",
                    "placeholder",
                    "--output-dir",
                    str(Path(tmpdir) / "runs"),
                ],
                cwd=BACKEND_ROOT,
                check=False,
                capture_output=True,
                text=True,
            )

        self.assertEqual(result.returncode, 0, result.stderr)
        event = json.loads(result.stdout.strip().splitlines()[-1])
        self.assertEqual(event["event"], "job.logged")
        job_dir = Path(event["logPath"])
        self.addCleanup(lambda: shutil.rmtree(job_dir, ignore_errors=True))

        self.assertTrue(job_dir.is_dir())
        for relative_path in EXPECTED_STAGE_FILES:
            self.assertTrue((job_dir / relative_path).is_file(), relative_path)

        html_dir = job_dir / "02_components" / "html"
        for filename in EXPECTED_COMPONENT_HTML:
            path = html_dir / filename
            self.assertTrue(path.is_file(), filename)
            self.assertIn("data-component-id", path.read_text(encoding="utf-8"))

        report_draft = (job_dir / "03_layout" / "report_draft.html").read_text(encoding="utf-8")
        self.assertIn("<!doctype html>", report_draft)
        self.assertIn("<style>", report_draft)
        self.assertIn("comp_data_kodex_us_sp500_2026_03_performance_chart", report_draft)
        self.assertIn("data-chart-placeholder", report_draft)
        self.assertNotIn("<canvas", report_draft.lower())
        self.assertNotIn("<svg", report_draft.lower())
        self.assertNotIn("<script", report_draft.lower())

    def test_cli_prints_stage_progress_events_before_final_result(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            result = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "report_engine",
                    "run",
                    "--dataset-id",
                    "data_kodex_us_sp500",
                    "--template-id",
                    "tpl_kb_monthly_guidebook",
                    "--month-id",
                    "2026-03",
                    "--component-mode",
                    "sample",
                    "--verification-mode",
                    "manual-pass",
                    "--renderer-mode",
                    "placeholder",
                    "--output-dir",
                    str(Path(tmpdir) / "runs"),
                ],
                cwd=BACKEND_ROOT,
                check=False,
                capture_output=True,
                text=True,
            )

        self.assertEqual(result.returncode, 0, result.stderr)
        events = [json.loads(line) for line in result.stdout.strip().splitlines()]
        final_event = events[-1]
        job_dir = Path(final_event["logPath"])
        self.addCleanup(lambda: shutil.rmtree(job_dir, ignore_errors=True))

        expected_stages = [
            "00_request",
            "01_template",
            "02_components",
            "03_layout",
            "04_render",
            "05_verification",
            "06_final",
        ]
        progress_events = [(event["event"], event.get("stage")) for event in events[:-1]]
        expected_progress = [
            (event_name, stage)
            for stage in expected_stages
            for event_name in ("stage.started", "stage.completed")
        ]
        self.assertEqual(progress_events, expected_progress)
        self.assertEqual(final_event["event"], "job.logged")

    def test_run_logs_do_not_include_llm_api_key_value(self):
        secret_value = "test-secret-value-for-log-redaction"
        with tempfile.TemporaryDirectory() as tmpdir:
            result = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "report_engine",
                    "run",
                    "--dataset-id",
                    "data_kodex_us_sp500",
                    "--template-id",
                    "tpl_kb_monthly_guidebook",
                    "--month-id",
                    "2026-03",
                    "--component-mode",
                    "sample",
                    "--verification-mode",
                    "manual-pass",
                    "--renderer-mode",
                    "placeholder",
                    "--output-dir",
                    str(Path(tmpdir) / "runs"),
                ],
                cwd=BACKEND_ROOT,
                check=False,
                capture_output=True,
                text=True,
                env={**__import__("os").environ, "LLM_API_KEY": secret_value},
            )

        self.assertEqual(result.returncode, 0, result.stderr)
        event = json.loads(result.stdout.strip().splitlines()[-1])
        job_dir = Path(event["logPath"])
        self.addCleanup(lambda: shutil.rmtree(job_dir, ignore_errors=True))

        combined = "\n".join(
            path.read_text(encoding="utf-8")
            for path in job_dir.rglob("*")
            if path.is_file()
        )
        self.assertNotIn(secret_value, combined)
        self.assertNotIn("LLM_API_KEY", combined)
        self.assertNotIn("apiKey", combined)

    def test_cli_placeholder_renderer_exercises_stage4_without_playwright(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            result = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "report_engine",
                    "run",
                    "--dataset-id",
                    "data_kodex_us_sp500",
                    "--template-id",
                    "tpl_kb_monthly_guidebook",
                    "--month-id",
                    "2026-03",
                    "--component-mode",
                    "sample",
                    "--verification-mode",
                    "manual-pass",
                    "--renderer-mode",
                    "placeholder",
                    "--output-dir",
                    str(Path(tmpdir) / "runs"),
                ],
                cwd=BACKEND_ROOT,
                check=False,
                capture_output=True,
                text=True,
            )

            self.assertEqual(result.returncode, 0, result.stdout)
            event = json.loads(result.stdout.strip().splitlines()[-1])
            job_dir = Path(event["logPath"])
            self.addCleanup(lambda: shutil.rmtree(job_dir, ignore_errors=True))

            render_result = json.loads((job_dir / "04_render" / "render_result.json").read_text(encoding="utf-8"))
            self.assertEqual(render_result["status"], "rendered")
            self.assertEqual(render_result["version"], 1)
            self.assertTrue(Path(render_result["htmlPath"]).is_file())
            self.assertTrue(Path(render_result["previewImagePath"]).is_file())
            report_html = Path(render_result["htmlPath"]).read_text(encoding="utf-8")
            self.assertTrue(render_result["chartRendered"])
            self.assertIn('data-chart-rendered="performance_chart"', report_html)
            self.assertNotIn("data-chart-placeholder", report_html)

    def test_run_supports_novita_component_mode_with_injected_fake_adapter(self):
        from report_engine.logging_flow import run_with_artifact_logging
        from report_engine.models import ReportJobRequest

        request = ReportJobRequest(
            datasetId="data_kodex_us_sp500",
            templateId="tpl_kb_monthly_guidebook",
            monthId="2026-03",
            componentMode="novita",
            layoutMode="novita",
            verificationMode="manual-pass",
            maxIterations=3,
            outputDir="runs",
        )

        event = run_with_artifact_logging(
            request,
            backend_root=BACKEND_ROOT,
            llm_adapter=FakeTask6Adapter(),
            renderer=FakeStage4Renderer(),
        )
        job_dir = Path(event["logPath"])
        self.addCleanup(lambda: shutil.rmtree(job_dir, ignore_errors=True))
        self.addCleanup(lambda: shutil.rmtree(BACKEND_ROOT / "runs" / event["jobId"], ignore_errors=True))

        self.assertEqual(event["event"], "job.logged")
        components = json.loads((job_dir / "02_components" / "components.json").read_text(encoding="utf-8"))
        self.assertEqual([item["componentKey"] for item in components], [
            "performance_chart",
            "performance_summary",
            "top_holdings",
            "review",
            "outlook",
        ])
        report_draft = (job_dir / "03_layout" / "report_draft.html").read_text(encoding="utf-8")
        self.assertIn("<!doctype html>", report_draft)
        self.assertIn("<style>", report_draft)
        self.assertIn("comp_data_kodex_us_sp500_2026_03_outlook", report_draft)
        report_html = Path(event["reportHtmlPath"]).read_text(encoding="utf-8")
        self.assertIn('data-chart-rendered="performance_chart"', report_html)
        self.assertNotIn("data-chart-placeholder", report_html)

    def test_run_creates_stage4_version_artifacts_with_injected_renderer(self):
        from report_engine.logging_flow import run_with_artifact_logging
        from report_engine.models import ReportJobRequest

        with tempfile.TemporaryDirectory() as tmpdir:
            request = ReportJobRequest(
                datasetId="data_kodex_us_sp500",
                templateId="tpl_kb_monthly_guidebook",
                monthId="2026-03",
                componentMode="sample",
                layoutMode="novita",
                verificationMode="manual-pass",
                maxIterations=3,
                outputDir=str(Path(tmpdir) / "runs"),
            )

            event = run_with_artifact_logging(
                request,
                backend_root=BACKEND_ROOT,
                renderer=FakeStage4Renderer(),
            )
            job_dir = Path(event["logPath"])
            self.addCleanup(lambda: shutil.rmtree(job_dir, ignore_errors=True))

            render_result = json.loads((job_dir / "04_render" / "render_result.json").read_text(encoding="utf-8"))
            final_result = json.loads((job_dir / "06_final" / "final_result.json").read_text(encoding="utf-8"))
            report_path = Path(render_result["htmlPath"])
            preview_path = Path(render_result["previewImagePath"])

            self.assertEqual(render_result["status"], "rendered")
            self.assertEqual(render_result["jobId"], event["jobId"])
            self.assertEqual(render_result["version"], 1)
            self.assertTrue(report_path.is_file())
            self.assertTrue(preview_path.is_file())
            report_html = report_path.read_text(encoding="utf-8")
            self.assertTrue(render_result["chartRendered"])
            self.assertIn('data-chart-rendered="performance_chart"', report_html)
            self.assertNotIn("data-chart-placeholder", report_html)
            self.assertEqual(preview_path.read_bytes(), b"png")
            self.assertEqual(final_result["version"], 1)
            self.assertEqual(final_result["reportHtmlPath"], str(report_path))
            self.assertEqual(final_result["previewImagePath"], str(preview_path))

    def test_run_reports_llm_request_and_response_progress_without_payloads(self):
        from report_engine.logging_flow import run_with_artifact_logging
        from report_engine.models import ReportJobRequest

        request = ReportJobRequest(
            datasetId="data_kodex_us_sp500",
            templateId="tpl_kb_monthly_guidebook",
            monthId="2026-03",
            componentMode="novita",
            layoutMode="novita",
            verificationMode="manual-pass",
            maxIterations=3,
            outputDir="runs",
        )
        events = []

        event = run_with_artifact_logging(
            request,
            backend_root=BACKEND_ROOT,
            llm_adapter=FakeTask6Adapter(),
            renderer=FakeStage4Renderer(),
            progress_callback=events.append,
        )
        job_dir = Path(event["logPath"])
        self.addCleanup(lambda: shutil.rmtree(job_dir, ignore_errors=True))
        self.addCleanup(lambda: shutil.rmtree(BACKEND_ROOT / "runs" / event["jobId"], ignore_errors=True))

        llm_events = [item for item in events if item["event"].startswith("llm.")]
        self.assertEqual([item["event"] for item in llm_events].count("llm.request.started"), 6)
        self.assertEqual([item["event"] for item in llm_events].count("llm.response.completed"), 6)
        self.assertEqual([item["task"] for item in llm_events if item["event"] == "llm.request.started"][:5], [
            "stage2_component",
            "stage2_component",
            "stage2_component",
            "stage2_component",
            "stage2_component",
        ])
        self.assertEqual(llm_events[-2]["stage"], "03_layout")
        self.assertEqual(llm_events[-2]["task"], "stage3_layout")
        self.assertEqual(llm_events[-1]["htmlChars"], len((job_dir / "03_layout" / "report_draft.html").read_text(encoding="utf-8")))

        combined_events = json.dumps(llm_events, ensure_ascii=False)
        self.assertNotIn("componentSource", combined_events)
        self.assertNotIn("promptInput", combined_events)
        self.assertNotIn("<section", combined_events)
        self.assertNotIn("apiKey", combined_events)
        self.assertNotIn("Authorization", combined_events)

    def test_stage3_correction_retry_progress_marks_second_layout_call_without_payloads(self):
        from report_engine.logging_flow import run_with_artifact_logging
        from report_engine.models import ReportJobRequest

        request = ReportJobRequest(
            datasetId="data_kodex_us_sp500",
            templateId="tpl_kb_monthly_guidebook",
            monthId="2026-03",
            componentMode="novita",
            layoutMode="novita",
            verificationMode="manual-pass",
            maxIterations=3,
            outputDir="runs",
        )
        adapter = Stage3CorrectionFakeAdapter()
        events = []

        event = run_with_artifact_logging(
            request,
            backend_root=BACKEND_ROOT,
            llm_adapter=adapter,
            renderer=FakeStage4Renderer(),
            progress_callback=events.append,
        )
        job_dir = Path(event["logPath"])
        self.addCleanup(lambda: shutil.rmtree(job_dir, ignore_errors=True))
        self.addCleanup(lambda: shutil.rmtree(BACKEND_ROOT / "runs" / event["jobId"], ignore_errors=True))

        stage3_requests = [
            item for item in events
            if item["event"] == "llm.request.started" and item["stage"] == "03_layout"
        ]
        stage3_completed = [
            item for item in events
            if item["event"] == "llm.response.completed" and item["stage"] == "03_layout"
        ]

        self.assertEqual(len(stage3_requests), 2)
        self.assertEqual(len(stage3_completed), 2)
        self.assertNotIn("correctionAttempt", stage3_requests[0])
        self.assertEqual(stage3_requests[1]["correctionAttempt"], 1)
        self.assertNotIn("correctionAttempt", stage3_completed[0])
        self.assertEqual(stage3_completed[1]["correctionAttempt"], 1)
        self.assertEqual(adapter.stage3_call_count, 2)

        combined_events = json.dumps(events, ensure_ascii=False)
        self.assertNotIn("promptInput", combined_events)
        self.assertNotIn("rejectedHtml", combined_events)
        self.assertNotIn("<section", combined_events)
        self.assertNotIn("data:image", combined_events)

    def test_llm_progress_wrapper_preserves_stage_batch_size_limit(self):
        from report_engine.logging_flow import run_with_artifact_logging
        from report_engine.models import ReportJobRequest

        request = ReportJobRequest(
            datasetId="data_kodex_us_sp500",
            templateId="tpl_kb_monthly_guidebook",
            monthId="2026-03",
            componentMode="novita",
            layoutMode="novita",
            verificationMode="manual-pass",
            maxIterations=3,
            outputDir="runs",
        )
        adapter = BatchLimitedFakeAdapter(stage_batch_size=2)

        event = run_with_artifact_logging(
            request,
            backend_root=BACKEND_ROOT,
            llm_adapter=adapter,
            renderer=FakeStage4Renderer(),
            progress_callback=lambda event: None,
        )
        job_dir = Path(event["logPath"])
        self.addCleanup(lambda: shutil.rmtree(job_dir, ignore_errors=True))
        self.addCleanup(lambda: shutil.rmtree(BACKEND_ROOT / "runs" / event["jobId"], ignore_errors=True))

        self.assertEqual(adapter.max_active_calls, 2)

    def test_llm_failure_progress_includes_component_metadata(self):
        from report_engine.errors import ReportEngineError
        from report_engine.logging_flow import run_with_artifact_logging
        from report_engine.models import ReportJobRequest

        request = ReportJobRequest(
            datasetId="data_kodex_us_sp500",
            templateId="tpl_kb_monthly_guidebook",
            monthId="2026-03",
            componentMode="novita",
            layoutMode="novita",
            verificationMode="manual-pass",
            maxIterations=3,
            outputDir="runs",
        )
        events = []

        with self.assertRaises(ReportEngineError):
            run_with_artifact_logging(
                request,
                backend_root=BACKEND_ROOT,
                llm_adapter=FailingStage2Adapter(failing_key="review"),
                progress_callback=events.append,
            )
        if events:
            self.addCleanup(lambda: shutil.rmtree(BACKEND_ROOT / "log" / events[0]["jobId"], ignore_errors=True))

        failed_events = [item for item in events if item["event"] == "llm.response.failed"]
        self.assertEqual(len(failed_events), 1)
        self.assertEqual(failed_events[0]["componentKey"], "review")
        self.assertEqual(failed_events[0]["componentId"], "comp_data_kodex_us_sp500_2026_03_review")
        self.assertEqual(failed_events[0]["dataSourceId"], "ds_data_kodex_us_sp500_2026_03_review")
        self.assertEqual(failed_events[0]["errorCode"], "LLM_INVALID_JSON")

    def test_run_writes_detailed_llm_call_logs_without_stdout_payloads(self):
        from report_engine.llm import NovitaLlmAdapter
        from report_engine.logging_flow import run_with_artifact_logging
        from report_engine.models import ReportJobRequest
        from report_engine.settings import LlmSettings

        request = ReportJobRequest(
            datasetId="data_kodex_us_sp500",
            templateId="tpl_kb_monthly_guidebook",
            monthId="2026-03",
            componentMode="novita",
            layoutMode="novita",
            verificationMode="manual-pass",
            maxIterations=3,
            outputDir="runs",
        )
        settings = LlmSettings(
            model="qwen/test",
            baseUrl="https://api.novita.ai/openai",
            apiKey="secret-key-123",
            temperature=0.0,
            maxTokens=4096,
            timeoutSeconds=120,
            chunkSizeChars=12000,
            stageBatchSize=1,
        )
        adapter = NovitaLlmAdapter(settings, session=SequenceSession(_task7_responses()))
        events = []

        with patch.dict(os.environ, {"LLM_API_KEY": "secret-key-123"}):
            event = run_with_artifact_logging(
                request,
                backend_root=BACKEND_ROOT,
                llm_adapter=adapter,
                renderer=FakeStage4Renderer(),
                progress_callback=events.append,
            )
        job_dir = Path(event["logPath"])
        self.addCleanup(lambda: shutil.rmtree(job_dir, ignore_errors=True))
        self.addCleanup(lambda: shutil.rmtree(BACKEND_ROOT / "runs" / event["jobId"], ignore_errors=True))

        stage2_logs = sorted((job_dir / "02_components" / "llm_calls").glob("*.json"))
        stage3_logs = sorted((job_dir / "03_layout" / "llm_calls").glob("*.json"))
        self.assertEqual(len(stage2_logs), 5)
        self.assertEqual(len(stage3_logs), 1)

        first_stage2 = json.loads(stage2_logs[0].read_text(encoding="utf-8"))
        stage3 = json.loads(stage3_logs[0].read_text(encoding="utf-8"))
        self.assertEqual(first_stage2["stage"], "02_components")
        self.assertEqual(first_stage2["task"], "stage2_component")
        self.assertEqual(first_stage2["status"], "completed")
        self.assertGreaterEqual(first_stage2["durationMs"], 0)
        self.assertIn("messages", first_stage2["request"])
        self.assertIn("componentSource", first_stage2["request"]["messages"][1]["content"])
        self.assertIn("data-component-id", first_stage2["response"]["content"])
        self.assertEqual(first_stage2["tokenUsage"], {"prompt_tokens": 10, "completion_tokens": 5, "total_tokens": 15})
        self.assertEqual(stage3["stage"], "03_layout")
        self.assertEqual(stage3["task"], "stage3_layout")
        self.assertIn("<!doctype html>", stage3["response"]["content"])
        self.assertEqual(stage3["request"]["messages"][1]["content"][1]["image_url"]["url"], "<image data redacted>")
        self.assertEqual(stage3["request"]["messages"][1]["content"][1]["image_url"]["mimeType"], "image/png")

        stdout_events = json.dumps(events, ensure_ascii=False)
        self.assertNotIn("componentSource", stdout_events)
        self.assertNotIn("promptInput", stdout_events)
        self.assertNotIn("<section", stdout_events)
        self.assertNotIn("data:image", stdout_events)

        combined_logs = "\n".join(path.read_text(encoding="utf-8") for path in stage2_logs + stage3_logs)
        self.assertNotIn("secret-key-123", combined_logs)
        self.assertNotIn("Authorization", combined_logs)
        self.assertNotIn("apiKey", combined_logs)
        self.assertNotIn("data:image", combined_logs)

    def test_report_draft_escapes_product_name_metadata(self):
        component = Stage2Component(
            componentId="comp_x",
            componentKey="review",
            datasetId="data_x",
            monthId="2026-03",
            dataSourceId="ds_x",
            renderType="list",
            html='<section data-component-id="comp_x"><p>OK</p></section>',
            chartSpec=None,
            styled=False,
        )

        html = _build_report_draft_html('Kodex "S&P<500>"', [component])

        self.assertIn("<title>Kodex &quot;S&amp;P&lt;500&gt;&quot;</title>", html)
        self.assertIn('data-report-product="Kodex &quot;S&amp;P&lt;500&gt;&quot;"', html)
        self.assertIn('<section data-component-id="comp_x"><p>OK</p></section>', html)


def _valid_test_chart_spec():
    return {
        "type": "line",
        "unit": "%",
        "labels": ["1개월", "3개월", "6개월"],
        "series": [
            {"name": "Kodex 미국 S&P500", "values": [1.4, 8.9, -1.4]},
            {"name": "BM", "values": [1.6, 9.2, -1.8]},
        ],
    }


class FakeTask6Adapter:
    def generate_stage2_component(self, component_source):
        dataset_id = component_source["datasetRef"]["datasetId"]
        month_id = component_source["snapshotRef"]["monthId"]
        component_key = component_source["componentKey"]
        component_id = f"comp_{dataset_id}_{month_id.replace('-', '_')}_{component_key}"
        chart_spec = _valid_test_chart_spec() if component_key == "performance_chart" else None
        return {
            "html": f'<section data-component-id="{component_id}"><p>{component_key}</p></section>',
            "chartSpec": chart_spec,
            "styled": False,
        }

    def generate_stage3_layout(self, prompt_input, template_image_data_url=None):
        body = "\n".join(item["html"] for item in prompt_input["components"])
        return f"<!doctype html><html><head><style>body {{ margin: 0; }}</style></head><body>{body}</body></html>"


class Stage3CorrectionFakeAdapter(FakeTask6Adapter):
    def __init__(self):
        self.stage3_call_count = 0

    def generate_stage3_layout(self, prompt_input, template_image_data_url=None):
        self.stage3_call_count += 1
        body = "\n".join(item["html"] for item in prompt_input["components"])
        if self.stage3_call_count == 1:
            return f"<!doctype html><html><body>{body}</body></html>"
        return f"<!doctype html><html><head><style>body {{ margin: 0; }}</style></head><body>{body}</body></html>"


class BatchLimitedFakeAdapter(FakeTask6Adapter):
    def __init__(self, stage_batch_size):
        self.settings = SimpleNamespace(stageBatchSize=stage_batch_size)
        self.active_calls = 0
        self.max_active_calls = 0
        self.lock = Lock()

    def generate_stage2_component(self, component_source):
        with self.lock:
            self.active_calls += 1
            self.max_active_calls = max(self.max_active_calls, self.active_calls)
        try:
            sleep(0.03)
            return super().generate_stage2_component(component_source)
        finally:
            with self.lock:
                self.active_calls -= 1


class FailingStage2Adapter(FakeTask6Adapter):
    def __init__(self, failing_key):
        self.failing_key = failing_key

    def generate_stage2_component(self, component_source):
        if component_source["componentKey"] == self.failing_key:
            from report_engine.errors import ErrorCode, ReportEngineError

            raise ReportEngineError(ErrorCode.LLM_INVALID_JSON, "synthetic failure", stage="llm")
        return super().generate_stage2_component(component_source)


class FakeStage4Renderer:
    def render_html_to_png(self, html_path, preview_path):
        Path(preview_path).write_bytes(b"png")
        return Path(preview_path)


def _task7_responses():
    dataset_id = "data_kodex_us_sp500"
    month_id = "2026-03"
    component_keys = [
        "performance_chart",
        "performance_summary",
        "top_holdings",
        "review",
        "outlook",
    ]
    responses = []
    component_html = []
    for key in component_keys:
        component_id = f"comp_{dataset_id}_{month_id.replace('-', '_')}_{key}"
        chart_spec = _valid_test_chart_spec() if key == "performance_chart" else None
        html = f'<section data-component-id="{component_id}"><p>{key}</p></section>'
        component_html.append(html)
        responses.append(
            FakeResponse(
                json.dumps({"html": html, "chartSpec": chart_spec, "styled": False}, ensure_ascii=False),
                usage={"prompt_tokens": 10, "completion_tokens": 5, "total_tokens": 15},
            )
        )
    chart_id = f"comp_{dataset_id}_{month_id.replace('-', '_')}_performance_chart"
    layout_html = (
        "<!doctype html><html><head><style>body { margin: 0; }</style></head><body>"
        f'<section data-component-id="{chart_id}"><div data-chart-placeholder="{chart_id}"></div></section>'
        + "\n".join(component_html[1:])
        + "</body></html>"
    )
    responses.append(FakeResponse(layout_html, usage={"prompt_tokens": 50, "completion_tokens": 40, "total_tokens": 90}))
    return responses


class FakeResponse:
    def __init__(self, content, status_code=200, usage=None):
        self.content = content
        self.status_code = status_code
        self.text = content
        self.usage = usage

    def raise_for_status(self):
        if self.status_code >= 400:
            import requests

            raise requests.exceptions.HTTPError(f"HTTP {self.status_code}")
        return None

    def json(self):
        payload = {"choices": [{"message": {"content": self.content}, "finish_reason": "stop"}]}
        if self.usage is not None:
            payload["usage"] = self.usage
        return payload


class SequenceSession:
    def __init__(self, responses):
        self.responses = list(responses)
        self.closed = False

    def post(self, url, headers, json, timeout):
        self.last_url = url
        self.last_headers = headers
        self.last_payload = json
        self.last_timeout = timeout
        return self.responses.pop(0)

    def close(self):
        self.closed = True


if __name__ == "__main__":
    unittest.main()
