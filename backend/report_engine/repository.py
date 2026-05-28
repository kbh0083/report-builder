import json
from pathlib import Path
from typing import Any

from .errors import ErrorCode, ReportEngineError
from .models import DatasetContext, PageSettings, Stage2Component, TemplateContext


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
