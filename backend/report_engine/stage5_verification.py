import json
import struct
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Protocol

from .errors import ErrorCode, ReportEngineError
from .models import ReportVersion, TemplateContext, VerificationMode, VerificationResult


class Stage5VerificationAdapter(Protocol):
    def verify_report_version(
        self,
        report_version: ReportVersion,
        *,
        template_context: TemplateContext | None = None,
    ) -> VerificationResult | dict[str, Any]:
        """Return visual verification result for a rendered report version."""


RevisionFactory = Callable[[ReportVersion, VerificationResult, int], ReportVersion]

_ISSUE_SEVERITY_SCORE = {
    "critical": 10,
    "major": 3,
    "minor": 1,
}
_DIMENSION_DRIFT_PENALTY = 9
_MAX_PREVIEW_DIMENSION_DRIFT_RATIO = 0.15


@dataclass(frozen=True)
class VerificationAttempt:
    reportVersion: ReportVersion
    result: VerificationResult
    verificationPath: str
    mode: str = ""
    verifiedAt: str = ""
    score: int = 0
    regressedFromVersion: int | None = None

    def to_json(self) -> dict[str, Any]:
        return _verification_payload(
            self.reportVersion,
            self.result,
            mode=self.mode,
            verified_at=self.verifiedAt,
            score=self.score,
            regressed_from_version=self.regressedFromVersion,
        )


@dataclass(frozen=True)
class VerificationLoopResult:
    attempts: list[VerificationAttempt]
    passedVersion: ReportVersion | None
    passedAttempt: VerificationAttempt | None
    bestFailedAttempt: VerificationAttempt | None = None
    bestFailedScore: int | None = None
    regressedVersions: list[dict[str, Any]] = field(default_factory=list)
    maxIterationsExceeded: bool = False

    @property
    def bestFailedVersion(self) -> ReportVersion | None:
        if self.bestFailedAttempt is None:
            return None
        return self.bestFailedAttempt.reportVersion


class Stage5VerificationService:
    def verify_until_passed(
        self,
        initial_version: ReportVersion,
        *,
        verification_mode: VerificationMode,
        max_iterations: int,
        adapter: Stage5VerificationAdapter | None = None,
        create_revision: RevisionFactory | None = None,
        template_context: TemplateContext | None = None,
    ) -> VerificationLoopResult:
        if max_iterations < 1:
            raise ReportEngineError(
                ErrorCode.VERIFICATION_MAX_ITERATIONS_EXCEEDED,
                "maxIterations must be at least 1",
                stage="stage5",
            )

        attempts: list[VerificationAttempt] = []
        baseline_size = _image_size(Path(initial_version.previewImagePath))
        max_dimension_drift_ratio = _max_preview_dimension_drift_ratio(template_context)
        best_failed_attempt: VerificationAttempt | None = None
        best_failed_score: int | None = None
        regressed_versions: list[dict[str, Any]] = []
        current_version = initial_version
        for iteration in range(1, max_iterations + 1):
            result = self._verify_version(current_version, verification_mode, adapter, template_context)
            current_size = _image_size(Path(current_version.previewImagePath))
            score = _verification_score(result, baseline_size, current_size, max_dimension_drift_ratio)
            regressed_from_version = (
                best_failed_attempt.reportVersion.version
                if not result.passed
                and best_failed_attempt is not None
                and best_failed_score is not None
                and score > best_failed_score
                else None
            )
            attempt = self._write_verification(
                current_version,
                verification_mode,
                result,
                score=score,
                regressed_from_version=regressed_from_version,
            )
            attempts.append(attempt)
            if result.passed:
                return VerificationLoopResult(
                    attempts=attempts,
                    passedVersion=current_version,
                    passedAttempt=attempt,
                    bestFailedAttempt=best_failed_attempt,
                    bestFailedScore=best_failed_score,
                    regressedVersions=regressed_versions,
                )

            if best_failed_score is None or score < best_failed_score:
                best_failed_attempt = attempt
                best_failed_score = score
            elif regressed_from_version is not None:
                regressed_versions.append(
                    {
                        "version": current_version.version,
                        "regressedFromVersion": regressed_from_version,
                        "score": score,
                        "bestFailedScore": best_failed_score,
                    }
                )

            if not result.revisionInstruction:
                return VerificationLoopResult(
                    attempts=attempts,
                    passedVersion=None,
                    passedAttempt=None,
                    bestFailedAttempt=best_failed_attempt,
                    bestFailedScore=best_failed_score,
                    regressedVersions=regressed_versions,
                )

            if iteration >= max_iterations:
                return VerificationLoopResult(
                    attempts=attempts,
                    passedVersion=None,
                    passedAttempt=None,
                    bestFailedAttempt=best_failed_attempt,
                    bestFailedScore=best_failed_score,
                    regressedVersions=regressed_versions,
                    maxIterationsExceeded=True,
                )
            if create_revision is None:
                raise ReportEngineError(
                    ErrorCode.CONFIG_INVALID,
                    "Novita verification requested a revision but no revision factory was provided",
                    stage="stage5",
                )

            revision_base_attempt = best_failed_attempt or attempt
            next_version = create_revision(
                revision_base_attempt.reportVersion,
                revision_base_attempt.result,
                current_version.version + 1,
            )
            self._validate_revision(current_version, next_version)
            current_version = next_version

        return VerificationLoopResult(
            attempts=attempts,
            passedVersion=None,
            passedAttempt=None,
            bestFailedAttempt=best_failed_attempt,
            bestFailedScore=best_failed_score,
            regressedVersions=regressed_versions,
        )

    def _verify_version(
        self,
        report_version: ReportVersion,
        verification_mode: VerificationMode,
        adapter: Stage5VerificationAdapter | None,
        template_context: TemplateContext | None,
    ) -> VerificationResult:
        self._validate_version_files(report_version)
        if verification_mode == "manual-pass":
            return VerificationResult(passed=True, issues=[])
        if verification_mode != "novita":
            raise ReportEngineError(
                ErrorCode.CONFIG_INVALID,
                f"Unsupported verification mode: {verification_mode}",
                stage="stage5",
            )
        if adapter is None or not hasattr(adapter, "verify_report_version"):
            raise ReportEngineError(
                ErrorCode.CONFIG_INVALID,
                "Novita verification requires an adapter with verify_report_version",
                stage="stage5",
            )
        return self._normalize_result(adapter.verify_report_version(report_version, template_context=template_context))

    def _write_verification(
        self,
        report_version: ReportVersion,
        verification_mode: VerificationMode,
        result: VerificationResult,
        *,
        score: int = 0,
        regressed_from_version: int | None = None,
    ) -> VerificationAttempt:
        verified_at = _now_iso()
        version_dir = Path(report_version.htmlPath).parent
        verification_path = version_dir / "verification.json"
        version_dir.mkdir(parents=True, exist_ok=True)
        verification_path.write_text(
            json.dumps(
                _verification_payload(
                    report_version,
                    result,
                    mode=verification_mode,
                    verified_at=verified_at,
                    score=score,
                    regressed_from_version=regressed_from_version,
                ),
                ensure_ascii=False,
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )
        return VerificationAttempt(
            reportVersion=report_version,
            result=result,
            verificationPath=str(verification_path),
            mode=verification_mode,
            verifiedAt=verified_at,
            score=score,
            regressedFromVersion=regressed_from_version,
        )

    def _normalize_result(self, raw: VerificationResult | dict[str, Any]) -> VerificationResult:
        if isinstance(raw, VerificationResult):
            return raw
        if not isinstance(raw, dict):
            raise ReportEngineError(
                ErrorCode.CONFIG_INVALID,
                "Verification adapter must return VerificationResult or dict",
                stage="stage5",
            )
        issues = raw.get("issues", [])
        if not isinstance(issues, list):
            raise ReportEngineError(
                ErrorCode.CONFIG_INVALID,
                "Verification issues must be a list",
                stage="stage5",
            )
        revision_instruction = raw.get("revisionInstruction")
        if revision_instruction is not None and not isinstance(revision_instruction, str):
            raise ReportEngineError(
                ErrorCode.CONFIG_INVALID,
                "revisionInstruction must be a string when present",
                stage="stage5",
            )
        return VerificationResult(
            passed=bool(raw.get("passed", False)),
            issues=issues,
            revisionInstruction=revision_instruction if revision_instruction else None,
        )

    def _validate_version_files(self, report_version: ReportVersion) -> None:
        for path in (Path(report_version.htmlPath), Path(report_version.previewImagePath)):
            if not path.is_file() or path.stat().st_size <= 0:
                raise ReportEngineError(
                    ErrorCode.CONFIG_INVALID,
                    f"Report version asset is missing: {path}",
                    stage="stage5",
                )

    def _validate_revision(self, current_version: ReportVersion, next_version: ReportVersion) -> None:
        if next_version.jobId != current_version.jobId:
            raise ReportEngineError(
                ErrorCode.CONFIG_INVALID,
                "Revision version must keep the same jobId",
                stage="stage5",
            )
        if next_version.version <= current_version.version:
            raise ReportEngineError(
                ErrorCode.CONFIG_INVALID,
                "Revision version must increment the version number",
                stage="stage5",
            )


def _verification_payload(
    report_version: ReportVersion,
    result: VerificationResult,
    *,
    mode: str,
    verified_at: str,
    score: int = 0,
    regressed_from_version: int | None = None,
) -> dict[str, Any]:
    payload = {
        "mode": mode,
        "jobId": report_version.jobId,
        "version": report_version.version,
        "passed": result.passed,
        "issues": result.issues,
        "verificationScore": score,
        "reportHtmlPath": report_version.htmlPath,
        "previewImagePath": report_version.previewImagePath,
        "verifiedAt": verified_at,
    }
    if regressed_from_version is not None:
        payload["regressedFromVersion"] = regressed_from_version
    if result.revisionInstruction:
        payload["revisionInstruction"] = result.revisionInstruction
    return payload


def _now_iso() -> str:
    return datetime.now().astimezone().isoformat(timespec="seconds")


def _verification_score(
    result: VerificationResult,
    baseline_size: tuple[int, int] | None,
    current_size: tuple[int, int] | None,
    max_dimension_drift_ratio: float = _MAX_PREVIEW_DIMENSION_DRIFT_RATIO,
) -> int:
    if result.passed:
        return 0
    score = sum(_issue_score(issue) for issue in result.issues)
    if _dimension_drift_exceeded(baseline_size, current_size, max_dimension_drift_ratio):
        score += _DIMENSION_DRIFT_PENALTY
    return score


def _max_preview_dimension_drift_ratio(template_context: TemplateContext | None) -> float:
    profile = template_context.revisionProfile if template_context is not None else None
    if profile is None:
        return _MAX_PREVIEW_DIMENSION_DRIFT_RATIO
    ratio = profile.maxPreviewDimensionDriftRatio
    if ratio <= 0:
        return _MAX_PREVIEW_DIMENSION_DRIFT_RATIO
    return ratio


def _issue_score(issue: dict[str, Any]) -> int:
    severity = issue.get("severity")
    if isinstance(severity, str):
        return _ISSUE_SEVERITY_SCORE.get(severity.strip().lower(), 1)
    return 1


def _dimension_drift_exceeded(
    baseline_size: tuple[int, int] | None,
    current_size: tuple[int, int] | None,
    max_dimension_drift_ratio: float,
) -> bool:
    if baseline_size is None or current_size is None:
        return False
    baseline_width, baseline_height = baseline_size
    current_width, current_height = current_size
    if baseline_width <= 0 or baseline_height <= 0:
        return False
    width_drift = abs(current_width - baseline_width) / baseline_width
    height_drift = abs(current_height - baseline_height) / baseline_height
    return max(width_drift, height_drift) > max_dimension_drift_ratio


def _image_size(path: Path) -> tuple[int, int] | None:
    try:
        with path.open("rb") as handle:
            header = handle.read(24)
    except OSError:
        return None
    if len(header) >= 24 and header.startswith(b"\x89PNG\r\n\x1a\n"):
        return struct.unpack(">II", header[16:24])
    return None
