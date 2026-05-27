import re

from .errors import ErrorCode, ReportEngineError
from .models import Stage2Component
from .repository import ReportRepository


class Stage2ComponentService:
    COMPONENT_KEYS = ReportRepository.COMPONENT_KEYS
    _FORBIDDEN_HTML_PATTERN = re.compile(r"(<style\b|style\s*=|class\s*=)", re.IGNORECASE)

    def __init__(self, repository: ReportRepository):
        self.repository = repository

    def load_components(
        self,
        dataset_id: str,
        month_id: str,
        component_mode: str = "sample",
    ) -> list[Stage2Component]:
        if component_mode != "sample":
            raise ReportEngineError(
                ErrorCode.COMPONENT_SOURCE_INCOMPLETE,
                f"Unsupported componentMode in Task 5 scope: {component_mode}",
                stage="stage2",
            )
        components = self.repository.load_sample_components(dataset_id, month_id)
        self.validate_components(components)
        return components

    def validate_components(self, components: list[Stage2Component]) -> None:
        by_key = {component.componentKey: component for component in components}
        missing = [key for key in self.COMPONENT_KEYS if key not in by_key]
        if missing:
            raise self._invalid(f"Missing components: {', '.join(missing)}")

        ordered = [by_key[key] for key in self.COMPONENT_KEYS]
        for component in ordered:
            if component.styled:
                raise self._invalid(f"Styled component is not allowed: {component.componentId}")
            if self._FORBIDDEN_HTML_PATTERN.search(component.html):
                raise self._invalid(f"Forbidden style/class markup in component: {component.componentId}")

        performance_chart = by_key["performance_chart"]
        if not performance_chart.chartSpec:
            raise self._invalid("performance_chart must include chartSpec")

        for key in self.COMPONENT_KEYS[1:]:
            if by_key[key].chartSpec is not None:
                raise self._invalid(f"{key} must not include chartSpec")

    def _invalid(self, detail: str) -> ReportEngineError:
        return ReportEngineError(ErrorCode.COMPONENT_SOURCE_INCOMPLETE, detail, stage="stage2")
