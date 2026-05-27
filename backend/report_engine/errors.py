from enum import Enum


class ErrorCode(str, Enum):
    DATASET_NOT_FOUND = "DATASET_NOT_FOUND"
    TEMPLATE_NOT_FOUND = "TEMPLATE_NOT_FOUND"
    MONTH_NOT_FOUND = "MONTH_NOT_FOUND"
    COMPONENT_SOURCE_INCOMPLETE = "COMPONENT_SOURCE_INCOMPLETE"
    LAYOUT_GENERATION_INVALID = "LAYOUT_GENERATION_INVALID"
    RENDER_FAILED = "RENDER_FAILED"
    VERIFICATION_MAX_ITERATIONS_EXCEEDED = "VERIFICATION_MAX_ITERATIONS_EXCEEDED"
    NO_PASSED_VERSION = "NO_PASSED_VERSION"
    CONFIG_INVALID = "CONFIG_INVALID"


class ReportEngineError(Exception):
    def __init__(self, code: ErrorCode, detail: str, stage: str | None = None):
        self.code = code
        self.detail = detail
        self.stage = stage
        super().__init__(self.__str__())

    def __str__(self) -> str:
        if self.stage:
            return f"{self.code.value} at {self.stage}: {self.detail}"
        return f"{self.code.value}: {self.detail}"
