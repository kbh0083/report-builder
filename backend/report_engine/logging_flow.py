import base64
import json
import os
import time
from collections.abc import Callable
from contextlib import contextmanager
from dataclasses import asdict
from datetime import datetime
from html import escape
from pathlib import Path
from threading import Lock
from typing import Any
from uuid import uuid4

from .artifact_logger import ArtifactLogger
from .chart_renderer import ChartRenderer
from .errors import ErrorCode, ReportEngineError
from .llm import LlmAdapter, NovitaLlmAdapter
from .llm_call_logger import LlmCallLogger
from .models import ReportJobRequest, Stage2Component
from .repository import ReportRepository
from .renderer import HtmlRenderer, PlaywrightRenderer
from .settings import load_llm_settings, parse_env_file
from .stage1_template import Stage1TemplateService
from .stage2_components import Stage2ComponentService
from .stage3_layout import Stage3LayoutService, stage3_component_html
from .stage5_verification import Stage5VerificationService
from .stage6_finalize import Stage6Finalizer
from .version_store import VersionStore


ProgressCallback = Callable[[dict[str, object]], None]
_STAGE3_MAX_CORRECTION_ATTEMPTS = 3


class JobEventSink:
    def __init__(self, logger: ArtifactLogger, progress_callback: ProgressCallback | None):
        self.logger = logger
        self.progress_callback = progress_callback
        self._lock = Lock()

    def emit(self, event: dict[str, object]) -> None:
        self.record(event)
        if self.progress_callback is not None:
            self.progress_callback(event)

    def record(self, event: dict[str, object]) -> None:
        with self._lock:
            self.logger.append_json_line("events.jsonl", event)


def run_with_artifact_logging(
    request: ReportJobRequest,
    backend_root: str | Path | None = None,
    llm_adapter: LlmAdapter | None = None,
    renderer: HtmlRenderer | None = None,
    chart_renderer: ChartRenderer | None = None,
    progress_callback: ProgressCallback | None = None,
) -> dict[str, object]:
    job_started_at = _now_iso()
    job_started = time.perf_counter()
    backend_path = Path(backend_root) if backend_root else Path(__file__).resolve().parents[1]
    workspace_root = backend_path.parent
    job_id = _new_job_id()
    logger = ArtifactLogger(backend_path / "log", job_id, secrets=_collect_secret_values(backend_path))
    event_sink = JobEventSink(logger, progress_callback)
    llm_call_logger = LlmCallLogger(logger)
    active_llm_adapter = llm_adapter or _load_default_llm_adapter(backend_path, request, llm_call_logger)
    active_llm_adapter = _with_llm_call_logging(active_llm_adapter, llm_call_logger)
    active_llm_adapter = _with_llm_progress(active_llm_adapter, job_id, event_sink.emit)

    repository = ReportRepository(workspace_root)
    template_service = Stage1TemplateService(repository)
    component_service = Stage2ComponentService(repository, llm_adapter=active_llm_adapter)

    with _stage(event_sink.emit, job_id, "00_request"):
        logger.write_json("00_request/request.json", asdict(request))

    with _stage(event_sink.emit, job_id, "01_template"):
        dataset = repository.load_dataset(request.datasetId)
        month_snapshot = repository.load_month_snapshot(request.datasetId, request.monthId)
        template_context = template_service.load_template_context(request.templateId)
        logger.write_json("01_template/template_context.json", template_context)
        logger.write_json(
            "01_template/selection_context.json",
            _selection_context_payload(dataset, month_snapshot, template_context),
        )

    with _stage(event_sink.emit, job_id, "02_components"):
        component_sources = repository.load_component_sources(request.datasetId, request.monthId)
        logger.write_json("02_components/component_sources.json", component_sources)

        components = component_service.load_components(
            request.datasetId,
            request.monthId,
            component_mode=request.componentMode,
        )
        logger.write_json("02_components/components.json", components)
        _write_component_html(logger, components)

    with _stage(event_sink.emit, job_id, "03_layout"):
        layout_service = Stage3LayoutService(active_llm_adapter) if active_llm_adapter else None
        prompt_input = (
            layout_service.build_prompt_input(template_context, dataset, month_snapshot, components)
            if layout_service
            else _build_offline_prompt_input(template_context, dataset, month_snapshot, components)
        )
        logger.write_json("03_layout/prompt_input.json", prompt_input)

        template_image_data_url = _template_image_data_url(workspace_root, template_context) if layout_service else None
        stage3_attempt_recorder = _stage3_attempt_recorder(logger, _STAGE3_MAX_CORRECTION_ATTEMPTS)
        report_draft_html = (
            layout_service.generate_report_draft(
                prompt_input,
                components,
                template_image_data_url=template_image_data_url,
                max_correction_attempts=_STAGE3_MAX_CORRECTION_ATTEMPTS,
                attempt_recorder=stage3_attempt_recorder,
            )
            if layout_service
            else _build_report_draft_html(dataset.baseData["product"]["productName"], components)
        )
        draft_path = logger.write_html("03_layout/report_draft.html", report_draft_html)

    with _stage(event_sink.emit, job_id, "04_render"):
        active_renderer = renderer or PlaywrightRenderer()
        active_chart_renderer = chart_renderer or ChartRenderer()
        chart_html = active_chart_renderer.render_and_inject(
            report_draft_html,
            components,
            template_context=template_context,
        )
        chart_rendering = active_chart_renderer.describe_chart_rendering(
            components,
            template_context=template_context,
        )
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
                **chart_rendering,
                "reportDraftPath": str(draft_path),
            },
        )

    with _stage(event_sink.emit, job_id, "05_verification"):
        revision_factory = None
        if request.verificationMode == "novita":
            revision_factory = lambda failed_version, verification_result, next_version_number: _create_revision_version(
                layout_service=layout_service,
                prompt_input=prompt_input,
                components=components,
                template_image_data_url=template_image_data_url,
                chart_renderer=active_chart_renderer,
                template_context=template_context,
                renderer=active_renderer,
                version_store=version_store,
                logger=logger,
                job_id=job_id,
                failed_version=failed_version,
                verification_result=verification_result,
                next_version_number=next_version_number,
            )
        try:
            verification_loop = Stage5VerificationService().verify_until_passed(
                report_version,
                verification_mode=request.verificationMode,
                max_iterations=request.maxIterations,
                adapter=active_llm_adapter,
                create_revision=revision_factory,
                template_context=template_context,
            )
        except ReportEngineError as exc:
            verification_loop = getattr(exc, "verification_loop", None)
            if verification_loop is not None and getattr(verification_loop, "attempts", None):
                _write_verification_loop_artifacts(logger, request.verificationMode, verification_loop)
            raise
        _write_verification_loop_artifacts(logger, request.verificationMode, verification_loop)

    with _stage(event_sink.emit, job_id, "06_final"):
        final_report = Stage6Finalizer(_resolve_output_root(backend_path, request.outputDir)).finalize(
            job_id,
            verification_loop.attempts,
            allow_failed_fallback=bool(getattr(verification_loop, "maxIterationsExceeded", False)),
        )
        job_completed_at = _now_iso()
        total_duration_ms = max(1, round((time.perf_counter() - job_started) * 1000))
        total_duration = _format_duration_mm_ss(total_duration_ms)
        logger.write_json(
            "06_final/final_result.json",
            {
                **asdict(final_report),
                "version": final_report.sourceVersion,
                "status": "finalized",
                "jobStartedAt": job_started_at,
                "jobCompletedAt": job_completed_at,
                "totalDurationMs": total_duration_ms,
                "totalDuration": total_duration,
            },
        )

    final_event = {
        "event": "job.logged",
        "jobId": job_id,
        "logPath": str(logger.job_dir),
        "version": final_report.sourceVersion,
        "reportHtmlPath": final_report.reportHtmlPath,
        "previewImagePath": final_report.previewImagePath,
        "verificationPassed": final_report.verificationPassed,
        "finalizationReason": final_report.finalizationReason,
        "jobStartedAt": job_started_at,
        "jobCompletedAt": job_completed_at,
        "totalDurationMs": total_duration_ms,
        "totalDuration": total_duration,
    }
    event_sink.record(final_event)
    return final_event


def event_to_stdout_line(event: dict[str, Any]) -> str:
    return json.dumps(event, ensure_ascii=False)


def _new_job_id() -> str:
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    return f"job_{timestamp}_{uuid4().hex[:8]}"


def _now_iso() -> str:
    return datetime.now().astimezone().isoformat(timespec="seconds")


def _format_duration_mm_ss(duration_ms: int) -> str:
    total_seconds = max(0, duration_ms) // 1000
    minutes, seconds = divmod(total_seconds, 60)
    return f"{minutes:02d}:{seconds:02d}"


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

    def verify_report_version(self, report_version, *, template_context=None):
        verifier = getattr(self.delegate, "verify_report_version", None)
        if verifier is None:
            raise AttributeError("delegate does not implement verify_report_version")
        request_metadata = {
            "version": getattr(report_version, "version", None),
            "reportHtmlPath": getattr(report_version, "htmlPath", None),
            "previewImagePath": getattr(report_version, "previewImagePath", None),
            "templateId": getattr(template_context, "templateId", None),
            "templatePreviewImage": getattr(template_context, "previewImage", None),
        }
        return self._tracked_call(
            stage="05_verification",
            task="stage5_verification",
            request_metadata=request_metadata,
            call=lambda: verifier(report_version, template_context=template_context),
            response_metadata=self._stage5_response_metadata,
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
    def _stage5_response_metadata(result: Any) -> dict[str, object]:
        if isinstance(result, dict):
            issues = result.get("issues", [])
            return {
                "responseType": "object",
                "passed": bool(result.get("passed", False)),
                "issueCount": len(issues) if isinstance(issues, list) else 0,
                "revisionRequested": bool(result.get("revisionInstruction")),
            }
        issues = getattr(result, "issues", [])
        return {
            "responseType": type(result).__name__,
            "passed": bool(getattr(result, "passed", False)),
            "issueCount": len(issues) if isinstance(issues, list) else 0,
            "revisionRequested": bool(getattr(result, "revisionInstruction", None)),
        }

    @staticmethod
    def _error_metadata(exc: Exception) -> dict[str, object]:
        return {
            "errorType": type(exc).__name__,
            "errorCode": getattr(getattr(exc, "code", None), "value", None),
        }


@contextmanager
def _stage(progress_callback: ProgressCallback | None, job_id: str, stage: str):
    started_at = _now_iso()
    started = time.perf_counter()
    _emit_progress(
        progress_callback,
        {"event": "stage.started", "jobId": job_id, "stage": stage, "startedAt": started_at},
    )
    try:
        yield
    except Exception:
        _emit_progress(
            progress_callback,
            {
                "event": "stage.failed",
                "jobId": job_id,
                "stage": stage,
                "startedAt": started_at,
                "failedAt": _now_iso(),
                "durationMs": max(0, round((time.perf_counter() - started) * 1000)),
            },
        )
        raise
    _emit_progress(
        progress_callback,
        {
            "event": "stage.completed",
            "jobId": job_id,
            "stage": stage,
            "startedAt": started_at,
            "completedAt": _now_iso(),
            "durationMs": max(0, round((time.perf_counter() - started) * 1000)),
        },
    )


def _emit_progress(progress_callback: ProgressCallback | None, event: dict[str, object]) -> None:
    if progress_callback is not None:
        progress_callback(event)


def _write_component_html(logger: ArtifactLogger, components: list[Stage2Component]) -> None:
    for component in components:
        logger.write_html(f"02_components/html/{component.componentKey}.html", component.html)


def _stage3_attempt_recorder(logger: ArtifactLogger, max_correction_attempts: int) -> Callable[[dict[str, Any]], None]:
    attempts: list[dict[str, Any]] = []

    def record(attempt: dict[str, Any]) -> None:
        attempt_number = attempt.get("attempt")
        if not isinstance(attempt_number, int):
            return
        html = attempt.get("html")
        html_path = None
        if isinstance(html, str):
            html_path = logger.write_html(
                f"03_layout/attempts/attempt_{attempt_number}_report_draft.html",
                html,
            )
        payload = {
            key: value
            for key, value in attempt.items()
            if key != "html"
        }
        if html_path is not None:
            payload["htmlPath"] = str(html_path)
        attempts.append(payload)
        logger.write_json(
            "03_layout/layout_validation_loop.json",
            {
                "maxCorrectionAttempts": max_correction_attempts,
                "attemptCount": len(attempts),
                "passed": bool(attempts and attempts[-1].get("status") == "passed"),
                "attempts": attempts,
            },
        )

    return record


def _performance_chart_component_id(components: list[Stage2Component]) -> str:
    for component in components:
        if component.componentKey == "performance_chart":
            return component.componentId
    return ""


def _selection_context_payload(dataset, month_snapshot: dict[str, Any], template_context) -> dict[str, Any]:
    product = dataset.baseData.get("product", {}) if isinstance(dataset.baseData, dict) else {}
    sales_channel = dataset.baseData.get("salesChannel", {}) if isinstance(dataset.baseData, dict) else {}
    return {
        "dataset": {
            "datasetId": dataset.datasetId,
            "productName": product.get("productName"),
            "distributorName": sales_channel.get("distributorName"),
        },
        "template": asdict(template_context),
        "monthSnapshot": {
            "monthId": month_snapshot.get("monthId"),
            "asOf": month_snapshot.get("asOf"),
            "periodLabel": month_snapshot.get("periodLabel"),
        },
    }


def _verification_loop_payload(mode: str, verification_loop) -> dict[str, Any]:
    return {
        "mode": mode,
        "attemptCount": len(verification_loop.attempts),
        "passedVersion": (
            verification_loop.passedVersion.version
            if verification_loop.passedVersion is not None
            else None
        ),
        "bestFailedVersion": (
            verification_loop.bestFailedVersion.version
            if verification_loop.bestFailedVersion is not None
            else None
        ),
        "bestFailedScore": verification_loop.bestFailedScore,
        "maxIterationsExceeded": bool(getattr(verification_loop, "maxIterationsExceeded", False)),
        "regressedVersions": verification_loop.regressedVersions,
        "attempts": [
            {
                **attempt.to_json(),
                "verificationPath": attempt.verificationPath,
            }
            for attempt in verification_loop.attempts
        ],
    }


def _write_verification_loop_artifacts(logger: ArtifactLogger, mode: str, verification_loop) -> None:
    logger.write_json("05_verification/verification.json", verification_loop.attempts[-1].to_json())
    logger.write_json(
        "05_verification/verification_loop.json",
        _verification_loop_payload(mode, verification_loop),
    )


def _create_revision_version(
    *,
    layout_service: Stage3LayoutService | None,
    prompt_input: dict[str, Any],
    components: list[Stage2Component],
    template_image_data_url: str | None,
    chart_renderer: ChartRenderer,
    template_context,
    renderer: HtmlRenderer,
    version_store: VersionStore,
    logger: ArtifactLogger,
    job_id: str,
    failed_version,
    verification_result,
    next_version_number: int,
):
    if layout_service is None:
        raise ReportEngineError(
            ErrorCode.CONFIG_INVALID,
            "Novita verification revision requires a Stage 3 layout service",
            stage="stage5",
        )
    base_report_draft_html = _read_base_report_draft_html(logger, failed_version.version)
    verification_correction = {
        "fromVersion": failed_version.version,
        "baseVersion": failed_version.version,
        "nextVersion": next_version_number,
        "revisionMode": "minimal_patch",
        "issues": verification_result.issues,
        "revisionInstruction": verification_result.revisionInstruction,
        "baseReportDraftHtml": base_report_draft_html,
        "basePreviewSize": _image_size_payload(failed_version.previewImagePath),
        "revisionContract": _stage5_revision_contract(components),
    }
    revision_profile = _template_revision_profile_payload(template_context)
    if revision_profile is not None:
        verification_correction["revisionProfile"] = revision_profile
    revision_prompt_input = {
        **prompt_input,
        "verificationCorrection": verification_correction,
    }
    revision_prefix = f"05_verification/revisions/v{next_version_number}"
    logger.write_json(f"{revision_prefix}_prompt_input.json", revision_prompt_input)
    revised_draft_html = layout_service.generate_report_draft(
        revision_prompt_input,
        components,
        template_image_data_url=template_image_data_url,
    )
    revised_chart_html = chart_renderer.render_and_inject(
        revised_draft_html,
        components,
        template_context=template_context,
    )
    chart_rendering = chart_renderer.describe_chart_rendering(
        components,
        template_context=template_context,
    )
    revised_version = version_store.create_version(job_id, next_version_number, revised_chart_html, renderer)
    draft_path = logger.write_html(f"{revision_prefix}_report_draft.html", revised_draft_html)
    logger.write_json(
        f"{revision_prefix}_render_result.json",
        {
            **asdict(revised_version),
            "status": "rendered",
            "chartRendered": True,
            "chartComponentId": _performance_chart_component_id(components),
            **chart_rendering,
            "reportDraftPath": str(draft_path),
            "revisionFromVersion": failed_version.version,
        },
    )
    return revised_version


def _read_base_report_draft_html(logger: ArtifactLogger, version: int) -> str:
    relative_path = (
        Path("03_layout/report_draft.html")
        if version == 1
        else Path(f"05_verification/revisions/v{version}_report_draft.html")
    )
    path = logger.job_dir / relative_path
    try:
        return path.read_text(encoding="utf-8")
    except OSError as exc:
        raise ReportEngineError(
            ErrorCode.CONFIG_INVALID,
            f"Revision base draft HTML could not be read: {relative_path}",
            stage="stage5",
        ) from exc


def _image_size_payload(path: str) -> dict[str, int] | None:
    size = _png_size(Path(path))
    if size is None:
        return None
    width, height = size
    return {"width": width, "height": height}


def _png_size(path: Path) -> tuple[int, int] | None:
    try:
        with path.open("rb") as handle:
            header = handle.read(24)
    except OSError:
        return None
    if len(header) >= 24 and header.startswith(b"\x89PNG\r\n\x1a\n"):
        import struct

        return struct.unpack(">II", header[16:24])
    return None


def _stage5_revision_contract(components: list[Stage2Component]) -> dict[str, Any]:
    return {
        "templateImageRole": "layout_and_style_only",
        "preserveAllStage2Components": True,
        "doNotCopyTemplateTextOrValues": True,
        "componentIds": [component.componentId for component in components],
        "componentKeys": [component.componentKey for component in components],
    }


def _template_revision_profile_payload(template_context) -> dict[str, Any] | None:
    profile = getattr(template_context, "revisionProfile", None)
    if profile is None:
        return None
    return {
        "revisionMode": profile.revisionMode,
        "preserveInitialGrid": profile.preserveInitialGrid,
        "maxPreviewDimensionDriftRatio": profile.maxPreviewDimensionDriftRatio,
        "allowedRevisionTargets": profile.allowedRevisionTargets,
        "forbiddenCssTokens": profile.forbiddenCssTokens,
    }


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
        "    :root { --report-primary: #4b5563; --report-accent: #f3f4f6; --chart-series-1: #4b5563; --chart-series-2: #9ca3af; }\n"
        "    * { box-sizing: border-box; }\n"
        "    @page { size: A4 portrait; margin: 0; }\n"
        "    body { margin: 0; background: #ededed; color: #111; font-family: \"Apple SD Gothic Neo\", \"Malgun Gothic\", Arial, sans-serif; line-height: 1.32; }\n"
        "    main[data-report-product] { width: 210mm; min-height: 297mm; margin: 24px auto; padding: 12mm 10mm 14mm; background: #fff; display: grid; gap: 6mm; }\n"
        "    section, article { break-inside: avoid; }\n"
        "    h2 { margin: 0 0 3mm; color: var(--report-primary); font-size: 5mm; }\n"
        "    table { width: 100%; border-collapse: collapse; font-size: 3.1mm; }\n"
        "    th { background: var(--report-primary); color: #fff; }\n"
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
