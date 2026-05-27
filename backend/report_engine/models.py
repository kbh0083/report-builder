from dataclasses import dataclass
from typing import Any, Literal


ComponentMode = Literal["sample", "novita"]
LayoutMode = Literal["novita"]
VerificationMode = Literal["manual-pass", "novita"]


@dataclass(frozen=True)
class PageSettings:
    size: str
    orientation: str


@dataclass(frozen=True)
class TemplateContext:
    templateId: str
    sourceHtml: str
    previewImage: str
    page: PageSettings
    name: str | None = None


@dataclass(frozen=True)
class DatasetContext:
    datasetId: str
    baseData: dict[str, Any]
    monthlySnapshots: list[dict[str, Any]]
    styleCandidates: dict[str, Any] | None = None
    schemaVersion: str | None = None


@dataclass(frozen=True)
class Stage2Component:
    componentId: str
    dataSourceId: str
    datasetId: str
    monthId: str
    componentKey: str
    renderType: str
    html: str
    chartSpec: dict[str, Any] | None
    styled: bool


@dataclass(frozen=True)
class ReportVersion:
    jobId: str
    version: int
    htmlPath: str
    previewImagePath: str
    status: str
    createdAt: str


@dataclass(frozen=True)
class VerificationResult:
    passed: bool
    issues: list[dict[str, Any]]
    revisionInstruction: str | None = None


@dataclass(frozen=True)
class ProgressEvent:
    event: str
    jobId: str
    stage: str
    payload: dict[str, Any]
    version: int | None = None


@dataclass(frozen=True)
class ReportJobRequest:
    datasetId: str
    templateId: str
    monthId: str
    componentMode: ComponentMode
    layoutMode: LayoutMode
    verificationMode: VerificationMode
    maxIterations: int
    outputDir: str

    def __post_init__(self) -> None:
        if self.componentMode not in ("sample", "novita"):
            raise ValueError("componentMode must be 'sample' or 'novita'")
        if self.layoutMode != "novita":
            raise ValueError("layoutMode must be 'novita'")
        if self.verificationMode not in ("manual-pass", "novita"):
            raise ValueError("verificationMode must be 'manual-pass' or 'novita'")
        if self.maxIterations < 1:
            raise ValueError("maxIterations must be greater than 0")
