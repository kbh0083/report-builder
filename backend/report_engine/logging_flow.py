import json
import os
from dataclasses import asdict
from datetime import datetime
from html import escape
from pathlib import Path
from uuid import uuid4

from .artifact_logger import ArtifactLogger
from .models import ReportJobRequest, Stage2Component
from .repository import ReportRepository
from .settings import parse_env_file
from .stage1_template import Stage1TemplateService
from .stage2_components import Stage2ComponentService


def run_with_artifact_logging(request: ReportJobRequest, backend_root: str | Path | None = None) -> dict[str, str]:
    backend_path = Path(backend_root) if backend_root else Path(__file__).resolve().parents[1]
    workspace_root = backend_path.parent
    job_id = _new_job_id()
    logger = ArtifactLogger(backend_path / "log", job_id, secrets=_collect_secret_values(backend_path))

    repository = ReportRepository(workspace_root)
    template_service = Stage1TemplateService(repository)
    component_service = Stage2ComponentService(repository)

    logger.write_json("00_request/request.json", asdict(request) | {"LLM_API_KEY": os.environ.get("LLM_API_KEY", "")})

    dataset = repository.load_dataset(request.datasetId)
    month_snapshot = repository.load_month_snapshot(request.datasetId, request.monthId)

    template_context = template_service.load_template_context(request.templateId)
    logger.write_json("01_template/template_context.json", template_context)

    component_sources = repository.load_component_sources(request.datasetId, request.monthId)
    logger.write_json("02_components/component_sources.json", component_sources)

    components = component_service.load_components(
        request.datasetId,
        request.monthId,
        component_mode=request.componentMode,
    )
    logger.write_json("02_components/components.json", components)
    _write_component_html(logger, components)

    prompt_input = {
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
        "llm": {
            "model": os.environ.get("LLM_MODEL", ""),
            "apiKey": os.environ.get("LLM_API_KEY", ""),
        },
    }
    logger.write_json("03_layout/prompt_input.json", prompt_input)

    report_draft_html = _build_report_draft_html(dataset.baseData["product"]["productName"], components)
    draft_path = logger.write_html("03_layout/report_draft.html", report_draft_html)

    logger.write_json(
        "04_render/render_result.json",
        {
            "status": "skipped",
            "reason": "Renderer is implemented in a later CLI stage.",
            "reportDraftPath": str(draft_path),
        },
    )
    logger.write_json(
        "05_verification/verification.json",
        {
            "mode": request.verificationMode,
            "passed": request.verificationMode == "manual-pass",
            "issues": [],
        },
    )
    logger.write_json(
        "06_final/final_result.json",
        {
            "status": "logged",
            "jobId": job_id,
            "reportDraftPath": str(draft_path),
        },
    )

    return {
        "event": "job.logged",
        "jobId": job_id,
        "logPath": str(logger.job_dir),
    }


def event_to_stdout_line(event: dict[str, str]) -> str:
    return json.dumps(event, ensure_ascii=False)


def _new_job_id() -> str:
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    return f"job_{timestamp}_{uuid4().hex[:8]}"


def _collect_secret_values(backend_root: Path) -> list[str]:
    env_values = parse_env_file(backend_root / ".env")
    secrets = [env_values.get("LLM_API_KEY", ""), os.environ.get("LLM_API_KEY", "")]
    return [secret for secret in secrets if secret]


def _write_component_html(logger: ArtifactLogger, components: list[Stage2Component]) -> None:
    for component in components:
        logger.write_html(f"02_components/html/{component.componentKey}.html", component.html)


def _build_report_draft_html(product_name: str, components: list[Stage2Component]) -> str:
    body = "\n".join(component.html for component in components)
    escaped_product_name = escape(product_name, quote=True)
    return (
        "<!doctype html>\n"
        '<html lang="ko">\n'
        "<head>\n"
        '  <meta charset="utf-8">\n'
        f"  <title>{escaped_product_name}</title>\n"
        "</head>\n"
        "<body>\n"
        f"  <main data-report-product=\"{escaped_product_name}\">\n"
        f"{body}\n"
        "  </main>\n"
        "</body>\n"
        "</html>\n"
    )
