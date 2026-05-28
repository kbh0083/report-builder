import base64
import json
import os
from collections.abc import Callable
from contextlib import contextmanager
from dataclasses import asdict
from datetime import datetime
from html import escape
from pathlib import Path
from typing import Any
from uuid import uuid4

from .artifact_logger import ArtifactLogger
from .chart_renderer import ChartRenderer
from .llm import LlmAdapter, NovitaLlmAdapter
from .llm_call_logger import LlmCallLogger
from .models import ReportJobRequest, Stage2Component
from .repository import ReportRepository
from .renderer import HtmlRenderer, PlaywrightRenderer
from .settings import load_llm_settings, parse_env_file
from .stage1_template import Stage1TemplateService
from .stage2_components import Stage2ComponentService
from .stage3_layout import Stage3LayoutService, stage3_component_html
from .version_store import VersionStore


ProgressCallback = Callable[[dict[str, object]], None]


def run_with_artifact_logging(
    request: ReportJobRequest,
    backend_root: str | Path | None = None,
    llm_adapter: LlmAdapter | None = None,
    renderer: HtmlRenderer | None = None,
    chart_renderer: ChartRenderer | None = None,
    progress_callback: ProgressCallback | None = None,
) -> dict[str, object]:
    backend_path = Path(backend_root) if backend_root else Path(__file__).resolve().parents[1]
    workspace_root = backend_path.parent
    job_id = _new_job_id()
    logger = ArtifactLogger(backend_path / "log", job_id, secrets=_collect_secret_values(backend_path))
    llm_call_logger = LlmCallLogger(logger)
    active_llm_adapter = llm_adapter or _load_default_llm_adapter(backend_path, request, llm_call_logger)
    active_llm_adapter = _with_llm_call_logging(active_llm_adapter, llm_call_logger)
    active_llm_adapter = _with_llm_progress(active_llm_adapter, job_id, progress_callback)

    repository = ReportRepository(workspace_root)
    template_service = Stage1TemplateService(repository)
    component_service = Stage2ComponentService(repository, llm_adapter=active_llm_adapter)

    with _stage(progress_callback, job_id, "00_request"):
        logger.write_json("00_request/request.json", asdict(request))

    with _stage(progress_callback, job_id, "01_template"):
        dataset = repository.load_dataset(request.datasetId)
        month_snapshot = repository.load_month_snapshot(request.datasetId, request.monthId)
        template_context = template_service.load_template_context(request.templateId)
        logger.write_json("01_template/template_context.json", template_context)

    with _stage(progress_callback, job_id, "02_components"):
        component_sources = repository.load_component_sources(request.datasetId, request.monthId)
        logger.write_json("02_components/component_sources.json", component_sources)

        components = component_service.load_components(
            request.datasetId,
            request.monthId,
            component_mode=request.componentMode,
        )
        logger.write_json("02_components/components.json", components)
        _write_component_html(logger, components)

    with _stage(progress_callback, job_id, "03_layout"):
        layout_service = Stage3LayoutService(active_llm_adapter) if active_llm_adapter else None
        prompt_input = (
            layout_service.build_prompt_input(template_context, dataset, month_snapshot, components)
            if layout_service
            else _build_offline_prompt_input(template_context, dataset, month_snapshot, components)
        )
        logger.write_json("03_layout/prompt_input.json", prompt_input)

        template_image_data_url = _template_image_data_url(workspace_root, template_context) if layout_service else None
        report_draft_html = (
            layout_service.generate_report_draft(prompt_input, components, template_image_data_url=template_image_data_url)
            if layout_service
            else _build_report_draft_html(dataset.baseData["product"]["productName"], components)
        )
        draft_path = logger.write_html("03_layout/report_draft.html", report_draft_html)

    with _stage(progress_callback, job_id, "04_render"):
        active_renderer = renderer or PlaywrightRenderer()
        active_chart_renderer = chart_renderer or ChartRenderer()
        chart_html = active_chart_renderer.render_and_inject(report_draft_html, components)
        chart_component_id = _performance_chart_component_id(components)
        version_store = VersionStore(_resolve_output_root(backend_path, request.outputDir))
        report_version = version_store.create_version(job_id, 1, chart_html, active_renderer)
        logger.write_json(
            "04_render/render_result.json",
            {
                **asdict(report_version),
                "status": "rendered",
                "chartRendered": True,
                "chartComponentId": chart_component_id,
                "reportDraftPath": str(draft_path),
            },
        )

    with _stage(progress_callback, job_id, "05_verification"):
        logger.write_json(
            "05_verification/verification.json",
            {
                "mode": request.verificationMode,
                "passed": request.verificationMode == "manual-pass",
                "issues": [],
            },
        )

    with _stage(progress_callback, job_id, "06_final"):
        logger.write_json(
            "06_final/final_result.json",
            {
                "status": "logged",
                "jobId": job_id,
                "reportDraftPath": str(draft_path),
                "version": report_version.version,
                "reportHtmlPath": report_version.htmlPath,
                "previewImagePath": report_version.previewImagePath,
            },
        )

    return {
        "event": "job.logged",
        "jobId": job_id,
        "logPath": str(logger.job_dir),
        "version": report_version.version,
        "reportHtmlPath": report_version.htmlPath,
        "previewImagePath": report_version.previewImagePath,
    }


def event_to_stdout_line(event: dict[str, Any]) -> str:
    return json.dumps(event, ensure_ascii=False)


def _new_job_id() -> str:
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    return f"job_{timestamp}_{uuid4().hex[:8]}"


def _collect_secret_values(backend_root: Path) -> list[str]:
    env_values = parse_env_file(backend_root / ".env")
    secrets = [env_values.get("LLM_API_KEY", ""), os.environ.get("LLM_API_KEY", "")]
    return [secret for secret in secrets if secret]


def _resolve_output_root(backend_path: Path, output_dir: str) -> Path:
    output_path = Path(output_dir)
    if output_path.is_absolute():
        return output_path
    return backend_path / output_path


def _load_default_llm_adapter(
    backend_root: Path,
    request: ReportJobRequest,
    llm_call_logger: LlmCallLogger,
) -> LlmAdapter | None:
    if request.componentMode == "novita" or request.verificationMode == "novita":
        return NovitaLlmAdapter(load_llm_settings(backend_root / ".env"), llm_call_logger=llm_call_logger)
    return None


def _with_llm_call_logging(
    llm_adapter: LlmAdapter | None,
    llm_call_logger: LlmCallLogger,
) -> LlmAdapter | None:
    if isinstance(llm_adapter, NovitaLlmAdapter) and llm_adapter.llm_call_logger is None:
        llm_adapter.llm_call_logger = llm_call_logger
    return llm_adapter


def _with_llm_progress(
    llm_adapter: LlmAdapter | None,
    job_id: str,
    progress_callback: ProgressCallback | None,
) -> LlmAdapter | None:
    if llm_adapter is None or progress_callback is None:
        return llm_adapter
    return LlmProgressAdapter(llm_adapter, job_id, progress_callback)


class LlmProgressAdapter:
    def __init__(self, delegate: LlmAdapter, job_id: str, progress_callback: ProgressCallback):
        self.delegate = delegate
        self.settings = getattr(delegate, "settings", None)
        self.job_id = job_id
        self.progress_callback = progress_callback

    def generate_stage2_component(self, component_source: dict[str, Any]) -> dict[str, Any]:
        request_metadata = {
            "componentKey": component_source.get("componentKey"),
            "componentId": component_source.get("componentId"),
            "dataSourceId": component_source.get("dataSourceId"),
        }
        return self._tracked_call(
            stage="02_components",
            task="stage2_component",
            request_metadata=request_metadata,
            call=lambda: self.delegate.generate_stage2_component(component_source),
            response_metadata=self._stage2_response_metadata,
        )

    def generate_stage3_layout(self, prompt_input: dict[str, Any], template_image_data_url: str | None = None) -> str:
        components = prompt_input.get("components", [])
        correction = prompt_input.get("correction")
        correction_attempt = correction.get("attempt") if isinstance(correction, dict) else None
        request_metadata = {
            "componentCount": len(components) if isinstance(components, list) else 0,
            "templateImageAttached": bool(template_image_data_url),
            "correctionAttempt": correction_attempt if isinstance(correction_attempt, int) else None,
        }
        return self._tracked_call(
            stage="03_layout",
            task="stage3_layout",
            request_metadata=request_metadata,
            call=lambda: self.delegate.generate_stage3_layout(
                prompt_input,
                template_image_data_url=template_image_data_url,
            ),
            response_metadata=self._stage3_response_metadata,
        )

    def _tracked_call(
        self,
        stage: str,
        task: str,
        request_metadata: dict[str, object],
        call: Callable[[], Any],
        response_metadata: Callable[[Any], dict[str, object]],
    ) -> Any:
        self._emit("llm.request.started", stage, task, request_metadata)
        try:
            result = call()
        except Exception as exc:
            self._emit("llm.response.failed", stage, task, request_metadata | self._error_metadata(exc))
            raise
        self._emit("llm.response.completed", stage, task, request_metadata | response_metadata(result))
        return result

    def _emit(self, event: str, stage: str, task: str, metadata: dict[str, object]) -> None:
        payload: dict[str, object] = {
            "event": event,
            "jobId": self.job_id,
            "stage": stage,
            "task": task,
        }
        model = self._model_name()
        if model:
            payload["model"] = model
        payload.update({key: value for key, value in metadata.items() if value is not None})
        self.progress_callback(payload)

    def _model_name(self) -> str | None:
        settings = getattr(self.delegate, "settings", None)
        model = getattr(settings, "model", None)
        return model if isinstance(model, str) and model else None

    @staticmethod
    def _stage2_response_metadata(result: Any) -> dict[str, object]:
        if not isinstance(result, dict):
            return {"responseType": type(result).__name__}
        html = result.get("html", "")
        return {
            "responseType": "object",
            "htmlChars": len(html) if isinstance(html, str) else 0,
            "chartSpecPresent": result.get("chartSpec") is not None,
            "styled": bool(result.get("styled", False)),
        }

    @staticmethod
    def _stage3_response_metadata(result: Any) -> dict[str, object]:
        return {
            "responseType": type(result).__name__,
            "htmlChars": len(result) if isinstance(result, str) else 0,
        }

    @staticmethod
    def _error_metadata(exc: Exception) -> dict[str, object]:
        return {
            "errorType": type(exc).__name__,
            "errorCode": getattr(getattr(exc, "code", None), "value", None),
        }


@contextmanager
def _stage(progress_callback: ProgressCallback | None, job_id: str, stage: str):
    _emit_progress(progress_callback, {"event": "stage.started", "jobId": job_id, "stage": stage})
    try:
        yield
    except Exception:
        _emit_progress(progress_callback, {"event": "stage.failed", "jobId": job_id, "stage": stage})
        raise
    _emit_progress(progress_callback, {"event": "stage.completed", "jobId": job_id, "stage": stage})


def _emit_progress(progress_callback: ProgressCallback | None, event: dict[str, object]) -> None:
    if progress_callback is not None:
        progress_callback(event)


def _write_component_html(logger: ArtifactLogger, components: list[Stage2Component]) -> None:
    for component in components:
        logger.write_html(f"02_components/html/{component.componentKey}.html", component.html)


def _performance_chart_component_id(components: list[Stage2Component]) -> str:
    for component in components:
        if component.componentKey == "performance_chart":
            return component.componentId
    return ""


def _build_offline_prompt_input(
    template_context,
    dataset,
    month_snapshot: dict,
    components: list[Stage2Component],
) -> dict:
    return {
        "dataset": {
            "datasetId": dataset.datasetId,
            "productName": dataset.baseData["product"]["productName"],
            "distributorName": dataset.baseData["salesChannel"]["distributorName"],
        },
        "template": asdict(template_context),
        "monthSnapshot": {
            "monthId": month_snapshot["monthId"],
            "asOf": month_snapshot["asOf"],
            "periodLabel": month_snapshot["periodLabel"],
        },
        "components": [{"componentId": item.componentId, "componentKey": item.componentKey} for item in components],
    }


def _build_report_draft_html(product_name: str, components: list[Stage2Component]) -> str:
    body = "\n".join(stage3_component_html(component) for component in components)
    escaped_product_name = escape(product_name, quote=True)
    return (
        "<!doctype html>\n"
        '<html lang="ko">\n'
        "<head>\n"
        '  <meta charset="utf-8">\n'
        f"  <title>{escaped_product_name}</title>\n"
        "  <style>\n"
        "    * { box-sizing: border-box; }\n"
        "    @page { size: A4 portrait; margin: 0; }\n"
        "    body { margin: 0; background: #ededed; color: #111; font-family: \"Apple SD Gothic Neo\", \"Malgun Gothic\", Arial, sans-serif; line-height: 1.32; }\n"
        "    main[data-report-product] { width: 210mm; min-height: 297mm; margin: 24px auto; padding: 12mm 10mm 14mm; background: #fff; display: grid; gap: 6mm; }\n"
        "    section, article { break-inside: avoid; }\n"
        "    h2 { margin: 0 0 3mm; color: #0258ff; font-size: 5mm; }\n"
        "    table { width: 100%; border-collapse: collapse; font-size: 3.1mm; }\n"
        "    th { background: #2d66f3; color: #fff; }\n"
        "    th, td { border: 0.25mm solid #c4c4c4; padding: 1.5mm 2mm; }\n"
        "    ul, ol, p { margin: 0 0 2.5mm; }\n"
        "    [data-chart-placeholder] { min-height: 58mm; border: 0.35mm dashed #8e8e8e; background: #f7f9ff; }\n"
        "    footer { margin-top: 8mm; padding-top: 3mm; border-top: 0.25mm solid #c4c4c4; font-size: 2.6mm; color: #555; }\n"
        "  </style>\n"
        "</head>\n"
        "<body>\n"
        f"  <main data-report-product=\"{escaped_product_name}\">\n"
        f"{body}\n"
        "    <footer>본 자료는 정보 제공 목적의 예시 리포트이며 투자 권유가 아닙니다.</footer>\n"
        "  </main>\n"
        "</body>\n"
        "</html>\n"
    )


def _template_image_data_url(workspace_root: Path, template_context) -> str:
    image_path = workspace_root / template_context.previewImage
    encoded = base64.b64encode(image_path.read_bytes()).decode("ascii")
    return f"data:{_image_mime_type(image_path)};base64,{encoded}"


def _image_mime_type(path: Path) -> str:
    suffix = path.suffix.lower()
    if suffix in {".jpg", ".jpeg"}:
        return "image/jpeg"
    if suffix == ".webp":
        return "image/webp"
    return "image/png"
