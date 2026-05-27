from pathlib import Path

from .errors import ErrorCode, ReportEngineError
from .models import TemplateContext
from .repository import ReportRepository


class Stage1TemplateService:
    def __init__(self, repository: ReportRepository):
        self.repository = repository

    def load_template_context(self, template_id: str) -> TemplateContext:
        context = self.repository.load_template(template_id)
        self.validate_template_context(context)
        return context

    def validate_template_context(self, context: TemplateContext) -> None:
        source_html = self._workspace_path(context.sourceHtml)
        preview_image = self._workspace_path(context.previewImage)
        if context.page.size != "A4" or context.page.orientation != "portrait":
            raise ReportEngineError(
                ErrorCode.TEMPLATE_NOT_FOUND,
                f"Unsupported page setting for templateId={context.templateId}: {context.page}",
                stage="stage1_template",
            )
        if not source_html.is_file():
            raise ReportEngineError(
                ErrorCode.TEMPLATE_NOT_FOUND,
                f"Template source HTML not found: {context.sourceHtml}",
                stage="stage1_template",
            )
        if not preview_image.is_file():
            raise ReportEngineError(
                ErrorCode.TEMPLATE_NOT_FOUND,
                f"Template preview image not found: {context.previewImage}",
                stage="stage1_template",
            )

    def _workspace_path(self, path: str) -> Path:
        return self.repository.workspace_root / path
