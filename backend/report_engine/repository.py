import json
from pathlib import Path
from typing import Any

from .errors import ErrorCode, ReportEngineError
from .models import (
    DatasetContext,
    PageSettings,
    Stage2Component,
    TemplateChartProfile,
    TemplateContext,
    TemplateRevisionProfile,
)


class ReportRepository:
    COMPONENT_KEYS = [
        "performance_chart",
        "performance_summary",
        "top_holdings",
        "review",
        "outlook",
    ]

    def __init__(self, root: str | Path):
        root_path = Path(root)
        if (root_path / "data" / "etf_data.json").exists():
            self.backend_root = root_path
            self.workspace_root = root_path.parent
        else:
            self.workspace_root = root_path
            self.backend_root = root_path / "backend"
        self.data_dir = self.backend_root / "data"

    def load_dataset(self, dataset_id: str) -> DatasetContext:
        bundle = self._load_json("etf_data.json")
        for item in bundle["datasets"]:
            if item["datasetId"] == dataset_id:
                return DatasetContext(
                    datasetId=item["datasetId"],
                    schemaVersion=item.get("schemaVersion"),
                    baseData=item["baseData"],
                    monthlySnapshots=item["monthlySnapshots"],
                )
        raise ReportEngineError(
            ErrorCode.DATASET_NOT_FOUND,
            f"Dataset not found: {dataset_id}",
            stage="repository",
        )

    def load_template(self, template_id: str) -> TemplateContext:
        catalog = self._load_json("report_templates.json")
        for item in catalog["templates"]:
            if item["templateId"] == template_id:
                page = item["page"]
                return TemplateContext(
                    templateId=item["templateId"],
                    name=item.get("name"),
                    previewImage=item["previewImage"],
                    page=PageSettings(size=page["size"], orientation=page["orientation"]),
                    chartProfile=self._template_chart_profile(item, item["templateId"]),
                    revisionProfile=self._template_revision_profile(item, item["templateId"]),
                )
        raise ReportEngineError(
            ErrorCode.TEMPLATE_NOT_FOUND,
            f"Template not found: {template_id}",
            stage="repository",
        )

    def load_month_snapshot(self, dataset_id: str, month_id: str) -> dict[str, Any]:
        dataset = self.load_dataset(dataset_id)
        for snapshot in dataset.monthlySnapshots:
            if snapshot["monthId"] == month_id:
                return snapshot
        raise ReportEngineError(
            ErrorCode.MONTH_NOT_FOUND,
            f"Month not found: datasetId={dataset_id}, monthId={month_id}",
            stage="repository",
        )

    def load_component_sources(self, dataset_id: str, month_id: str) -> list[dict[str, Any]]:
        catalog = self._load_json("etf_stage2_component_sources.json")
        matches = [
            item
            for item in catalog["componentSources"]
            if item["datasetRef"]["datasetId"] == dataset_id
            and item["snapshotRef"]["monthId"] == month_id
        ]
        return self._ordered_sources_or_error(matches, dataset_id, month_id)

    def load_sample_components(self, dataset_id: str, month_id: str) -> list[Stage2Component]:
        catalog = self._load_json("etf_stage2_components.sample.json")
        matches = [
            Stage2Component(
                componentId=item["componentId"],
                dataSourceId=item["dataSourceId"],
                datasetId=item["datasetId"],
                monthId=item["monthId"],
                componentKey=item["componentKey"],
                renderType=item["renderType"],
                html=item["html"],
                chartSpec=item.get("chartSpec"),
                styled=item["styled"],
            )
            for item in catalog["stage2Components"]
            if item["datasetId"] == dataset_id and item["monthId"] == month_id
        ]
        return self._ordered_components_or_error(matches, dataset_id, month_id)

    def _load_json(self, filename: str) -> dict[str, Any]:
        with (self.data_dir / filename).open(encoding="utf-8") as handle:
            return json.load(handle)

    def _template_chart_profile(
        self,
        item: dict[str, Any],
        template_id: str,
    ) -> dict[str, TemplateChartProfile]:
        raw_profile = item.get("chartProfile")
        if not isinstance(raw_profile, dict):
            raise self._config_invalid(f"Template chartProfile is required: {template_id}")
        performance_chart = raw_profile.get("performance_chart")
        if not isinstance(performance_chart, dict):
            raise self._config_invalid(f"Template chartProfile.performance_chart is required: {template_id}")

        has_chart = performance_chart.get("templateImageHasChart")
        if not isinstance(has_chart, bool):
            raise self._config_invalid(
                f"Template chartProfile.performance_chart.templateImageHasChart must be boolean: {template_id}"
            )
        fallback_type = performance_chart.get("fallbackChartType")
        if fallback_type not in {"bar", "line"}:
            raise self._config_invalid(
                f"Template chartProfile.performance_chart.fallbackChartType must be bar or line: {template_id}"
            )
        detected_type = performance_chart.get("detectedChartType")
        if detected_type is not None and detected_type not in {"bar", "line"}:
            raise self._config_invalid(
                f"Template chartProfile.performance_chart.detectedChartType must be null, bar, or line: {template_id}"
            )
        if has_chart and detected_type is None:
            raise self._config_invalid(
                f"Template chartProfile.performance_chart.detectedChartType is required when template has a chart: {template_id}"
            )

        return {
            "performance_chart": TemplateChartProfile(
                templateImageHasChart=has_chart,
                detectedChartType=detected_type,
                fallbackChartType=fallback_type,
            )
        }

    def _template_revision_profile(
        self,
        item: dict[str, Any],
        template_id: str,
    ) -> TemplateRevisionProfile | None:
        raw_profile = item.get("revisionProfile")
        if raw_profile is None:
            return None
        if not isinstance(raw_profile, dict):
            raise self._config_invalid(f"Template revisionProfile must be an object when present: {template_id}")

        revision_mode = raw_profile.get("revisionMode")
        if revision_mode != "minimal_patch":
            raise self._config_invalid(f"Template revisionProfile.revisionMode must be minimal_patch: {template_id}")
        preserve_initial_grid = raw_profile.get("preserveInitialGrid")
        if not isinstance(preserve_initial_grid, bool):
            raise self._config_invalid(
                f"Template revisionProfile.preserveInitialGrid must be boolean: {template_id}"
            )
        max_drift = raw_profile.get("maxPreviewDimensionDriftRatio")
        if not isinstance(max_drift, (int, float)) or isinstance(max_drift, bool) or max_drift <= 0:
            raise self._config_invalid(
                f"Template revisionProfile.maxPreviewDimensionDriftRatio must be a positive number: {template_id}"
            )
        allowed_targets = raw_profile.get("allowedRevisionTargets", [])
        forbidden_tokens = raw_profile.get("forbiddenCssTokens", [])
        if not _string_list(allowed_targets):
            raise self._config_invalid(
                f"Template revisionProfile.allowedRevisionTargets must be a list of strings: {template_id}"
            )
        if not _string_list(forbidden_tokens):
            raise self._config_invalid(
                f"Template revisionProfile.forbiddenCssTokens must be a list of strings: {template_id}"
            )
        return TemplateRevisionProfile(
            revisionMode=revision_mode,
            preserveInitialGrid=preserve_initial_grid,
            maxPreviewDimensionDriftRatio=float(max_drift),
            allowedRevisionTargets=list(allowed_targets),
            forbiddenCssTokens=list(forbidden_tokens),
        )

    @staticmethod
    def _config_invalid(detail: str) -> ReportEngineError:
        return ReportEngineError(ErrorCode.CONFIG_INVALID, detail, stage="repository")

    def _ordered_sources_or_error(
        self,
        sources: list[dict[str, Any]],
        dataset_id: str,
        month_id: str,
    ) -> list[dict[str, Any]]:
        by_key = {item["componentKey"]: item for item in sources}
        missing = [key for key in self.COMPONENT_KEYS if key not in by_key]
        if missing:
            raise ReportEngineError(
                ErrorCode.COMPONENT_SOURCE_INCOMPLETE,
                f"Missing component sources for datasetId={dataset_id}, monthId={month_id}: {', '.join(missing)}",
                stage="stage2",
            )
        return [by_key[key] for key in self.COMPONENT_KEYS]

    def _ordered_components_or_error(
        self,
        components: list[Stage2Component],
        dataset_id: str,
        month_id: str,
    ) -> list[Stage2Component]:
        by_key = {item.componentKey: item for item in components}
        missing = [key for key in self.COMPONENT_KEYS if key not in by_key]
        if missing:
            raise ReportEngineError(
                ErrorCode.COMPONENT_SOURCE_INCOMPLETE,
                f"Missing sample components for datasetId={dataset_id}, monthId={month_id}: {', '.join(missing)}",
                stage="stage2",
            )
        return [by_key[key] for key in self.COMPONENT_KEYS]


def _string_list(value: Any) -> bool:
    return isinstance(value, list) and all(isinstance(item, str) and item.strip() for item in value)
