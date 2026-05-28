import re
from concurrent.futures import ThreadPoolExecutor
from html.parser import HTMLParser
from typing import Any

from .errors import ErrorCode, ReportEngineError
from .llm import LlmAdapter
from .models import Stage2Component
from .repository import ReportRepository


class Stage2ComponentService:
    COMPONENT_KEYS = ReportRepository.COMPONENT_KEYS
    _FORBIDDEN_HTML_PATTERN = re.compile(r"(<style\b|style\s*=|class\s*=)", re.IGNORECASE)

    def __init__(self, repository: ReportRepository, llm_adapter: LlmAdapter | None = None):
        self.repository = repository
        self.llm_adapter = llm_adapter

    def load_components(
        self,
        dataset_id: str,
        month_id: str,
        component_mode: str = "sample",
    ) -> list[Stage2Component]:
        if component_mode == "sample":
            components = self.repository.load_sample_components(dataset_id, month_id)
            self.validate_components(components)
            return components
        if component_mode == "novita":
            components = self._generate_novita_components(dataset_id, month_id)
            self.validate_components(components)
            return components
        raise ReportEngineError(
            ErrorCode.COMPONENT_SOURCE_INCOMPLETE,
            f"Unsupported componentMode: {component_mode}",
            stage="stage2",
        )

    def _generate_novita_components(self, dataset_id: str, month_id: str) -> list[Stage2Component]:
        if self.llm_adapter is None:
            raise ReportEngineError(
                ErrorCode.CONFIG_INVALID,
                "componentMode=novita requires an LLM adapter",
                stage="stage2",
            )
        sources = self.repository.load_component_sources(dataset_id, month_id)
        with ThreadPoolExecutor(max_workers=self._parallel_worker_count(len(sources))) as executor:
            return list(executor.map(self._generate_component_from_source, sources))

    def _generate_component_from_source(self, source: dict[str, Any]) -> Stage2Component:
        if self.llm_adapter is None:
            raise self._invalid("LLM adapter is not configured")
        generated = self.llm_adapter.generate_stage2_component(self._prompt_source(source))
        return self._component_from_source(source, generated)

    def _component_from_source(self, source: dict[str, Any], generated: dict[str, Any]) -> Stage2Component:
        if not isinstance(generated, dict):
            raise self._invalid("LLM component response must be an object")
        html = generated.get("html")
        if not isinstance(html, str):
            raise self._invalid("LLM component response must include html text")
        dataset_id = source["datasetRef"]["datasetId"]
        month_id = source["snapshotRef"]["monthId"]
        component_key = source["componentKey"]
        return Stage2Component(
            componentId=self._component_id(dataset_id, month_id, component_key),
            dataSourceId=source["dataSourceId"],
            datasetId=dataset_id,
            monthId=month_id,
            componentKey=component_key,
            renderType=source["renderType"],
            html=html,
            chartSpec=generated.get("chartSpec"),
            styled=bool(generated.get("styled", False)),
        )

    def validate_components(self, components: list[Stage2Component]) -> None:
        if [component.componentKey for component in components] != self.COMPONENT_KEYS:
            raise self._invalid("Components must be in the expected componentKey order")
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
            if not self._has_component_id_marker(component):
                raise self._invalid(f"Missing data-component-id marker in component: {component.componentId}")

        performance_chart = by_key["performance_chart"]
        if not performance_chart.chartSpec:
            raise self._invalid("performance_chart must include chartSpec")

        for key in self.COMPONENT_KEYS[1:]:
            if by_key[key].chartSpec is not None:
                raise self._invalid(f"{key} must not include chartSpec")

    def _invalid(self, detail: str) -> ReportEngineError:
        return ReportEngineError(ErrorCode.COMPONENT_SOURCE_INCOMPLETE, detail, stage="stage2")

    def _parallel_worker_count(self, source_count: int) -> int:
        settings = getattr(self.llm_adapter, "settings", None)
        configured_limit = getattr(settings, "stageBatchSize", source_count)
        try:
            limit = int(configured_limit)
        except (TypeError, ValueError):
            limit = source_count
        return max(1, min(source_count, limit))

    def _prompt_source(self, source: dict[str, Any]) -> dict[str, Any]:
        dataset_id = source["datasetRef"]["datasetId"]
        month_id = source["snapshotRef"]["monthId"]
        component_key = source["componentKey"]
        return source | {"componentId": self._component_id(dataset_id, month_id, component_key)}

    @staticmethod
    def _component_id(dataset_id: str, month_id: str, component_key: str) -> str:
        return f"comp_{dataset_id}_{month_id.replace('-', '_')}_{component_key}"

    @staticmethod
    def _has_component_id_marker(component: Stage2Component) -> bool:
        parser = _ComponentIdMarkerParser(component.componentId)
        parser.feed(component.html)
        parser.close()
        return parser.found


class _ComponentIdMarkerParser(HTMLParser):
    def __init__(self, component_id: str):
        super().__init__(convert_charrefs=True)
        self.component_id = component_id
        self.found = False

    def handle_starttag(self, tag: str, attrs) -> None:
        self._check_attrs(attrs)

    def handle_startendtag(self, tag: str, attrs) -> None:
        self._check_attrs(attrs)

    def _check_attrs(self, attrs) -> None:
        for name, value in attrs:
            if name.lower() == "data-component-id" and value == self.component_id:
                self.found = True
                return
