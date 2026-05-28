import json
from collections.abc import Callable
from dataclasses import dataclass
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


RevisionFactory = Callable[[ReportVersion, VerificationResult], ReportVersion]


@dataclass(frozen=True)
class VerificationAttempt:
    reportVersion: ReportVersion
    result: VerificationResult
    verificationPath: str
    mode: str = ""
    verifiedAt: str = ""

    def to_json(self) -> dict[str, Any]:
        return _verification_payload(
            self.reportVersion,
            self.result,
            mode=self.mode,
            verified_at=self.verifiedAt,
        )


@dataclass(frozen=True)
class VerificationLoopResult:
    attempts: list[VerificationAttempt]
    passedVersion: ReportVersion | None
    passedAttempt: VerificationAttempt | None


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
        current_version = initial_version
        for iteration in range(1, max_iterations + 1):
            result = self._verify_version(current_version, verification_mode, adapter, template_context)
            attempt = self._write_verification(current_version, verification_mode, result)
            attempts.append(attempt)
            if result.passed:
                return VerificationLoopResult(
                    attempts=attempts,
                    passedVersion=current_version,
                    passedAttempt=attempt,
                )

            if not result.revisionInstruction:
                return VerificationLoopResult(attempts=attempts, passedVersion=None, passedAttempt=None)

            if iteration >= max_iterations:
                raise ReportEngineError(
                    ErrorCode.VERIFICATION_MAX_ITERATIONS_EXCEEDED,
                    "Verification requested another revision after maxIterations was reached",
                    stage="stage5",
                )
            if create_revision is None:
                raise ReportEngineError(
                    ErrorCode.CONFIG_INVALID,
                    "Novita verification requested a revision but no revision factory was provided",
                    stage="stage5",
                )

            next_version = create_revision(current_version, result)
            self._validate_revision(current_version, next_version)
            current_version = next_version

        return VerificationLoopResult(attempts=attempts, passedVersion=None, passedAttempt=None)

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
) -> dict[str, Any]:
    payload = {
        "mode": mode,
        "jobId": report_version.jobId,
        "version": report_version.version,
        "passed": result.passed,
        "issues": result.issues,
        "reportHtmlPath": report_version.htmlPath,
        "previewImagePath": report_version.previewImagePath,
        "verifiedAt": verified_at,
    }
    if result.revisionInstruction:
        payload["revisionInstruction"] = result.revisionInstruction
    return payload


def _now_iso() -> str:
    return datetime.now().astimezone().isoformat(timespec="seconds")
