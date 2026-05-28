import base64
import binascii
import json
import re
import time
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Protocol

import requests

from .errors import ErrorCode, ReportEngineError
from .models import ReportVersion, TemplateContext
from .prompt_store import PromptStore
from .settings import LlmSettings


@dataclass(frozen=True)
class LlmApiResponse:
    content: str
    finish_reason: str | None
    usage: dict[str, Any] | None


class LlmAdapter(Protocol):
    def generate_stage2_component(self, component_source: dict[str, Any]) -> dict[str, Any]:
        """Return the LLM-generated Stage 2 fields for one component source."""

    def generate_stage3_layout(self, prompt_input: dict[str, Any], template_image_data_url: str | None = None) -> str:
        """Return a single HTML report draft for Stage 3."""

    def verify_report_version(
        self,
        report_version: ReportVersion,
        *,
        template_context: TemplateContext | None = None,
    ) -> dict[str, Any]:
        """Return Stage 5 visual verification result for one rendered report version."""


class NovitaLlmAdapter:
    def __init__(
        self,
        settings: LlmSettings,
        session: Any | None = None,
        llm_call_logger: Any | None = None,
        prompt_store: PromptStore | None = None,
    ):
        self.settings = settings
        self.session = session
        self.llm_call_logger = llm_call_logger
        self.prompt_store = prompt_store or PromptStore()

    def generate_stage2_component(self, component_source: dict[str, Any]) -> dict[str, Any]:
        def generate() -> dict[str, Any]:
            def normalize_stage2(content: str) -> dict[str, Any]:
                result = self._normalize_stage2_component_content(content)
                if not isinstance(result, dict):
                    raise ReportEngineError(
                        ErrorCode.LLM_INVALID_JSON,
                        "LLM response JSON must be an object",
                        stage="llm",
                    )
                return result

            return self._post_chat(
                [
                    {
                        "role": "system",
                        "content": self.prompt_store.read_text("02_components_system.txt"),
                    },
                    {
                        "role": "user",
                        "content": json.dumps(
                            {
                                "task": "stage2_component",
                                "componentSource": component_source,
                            },
                            ensure_ascii=False,
                        ),
                    },
                ],
                response_format={"type": "json_object"},
                stage="02_components",
                task="stage2_component",
                label=str(component_source.get("componentKey") or "component"),
                transform=normalize_stage2,
            )

        return self._retry_invalid_json(generate)

    def generate_stage3_layout(self, prompt_input: dict[str, Any], template_image_data_url: str | None = None) -> str:
        return self._post_chat(
            [
                {
                    "role": "system",
                    "content": self.prompt_store.read_text("03_layout_system.txt"),
                },
                {
                    "role": "user",
                    "content": self._stage3_user_content(prompt_input, template_image_data_url),
                },
            ],
            response_format=None,
            stage="03_layout",
            task="stage3_layout",
            label="layout",
            transform=lambda content: content.strip(),
        )

    def verify_report_version(
        self,
        report_version: ReportVersion,
        *,
        template_context: TemplateContext | None = None,
    ) -> dict[str, Any]:
        def verify() -> dict[str, Any]:
            return self._post_chat(
                [
                    {
                        "role": "system",
                        "content": self.prompt_store.read_text("05_verification_system.txt"),
                    },
                    {
                        "role": "user",
                        "content": self._stage5_user_content(report_version, template_context),
                    },
                ],
                response_format={"type": "json_object"},
                stage="05_verification",
                task="stage5_verification",
                label=f"v{report_version.version}",
                transform=self._normalize_stage5_verification_content,
            )

        return self._retry_invalid_json(verify)

    def _post_chat(
        self,
        messages: list[dict[str, Any]],
        response_format: dict[str, str] | None,
        *,
        stage: str,
        task: str,
        label: str,
        transform: Callable[[str], Any],
    ) -> Any:
        payload: dict[str, Any] = {
            "model": self.settings.model,
            "messages": messages,
            "temperature": self.settings.temperature,
            "top_p": self.settings.topP,
            "top_k": self.settings.topK,
            "min_p": self.settings.minP,
            "presence_penalty": self.settings.presencePenalty,
            "repetition_penalty": self.settings.repetitionPenalty,
            "max_tokens": self.settings.maxTokens,
            "stream": False,
            "enable_thinking": self.settings.enableThinking,
            "separate_reasoning": self.settings.separateReasoning,
        }
        if response_format is not None:
            payload["response_format"] = response_format

        started_at = _now_iso()
        started = time.perf_counter()
        api_response: LlmApiResponse | None = None
        try:
            api_response = self._post_with_retries(payload)
            result = transform(api_response.content)
        except Exception as exc:
            self._write_llm_call_log(
                stage=stage,
                task=task,
                label=label,
                status="failed",
                started_at=started_at,
                started=started,
                request=payload,
                response=api_response,
                error=exc,
            )
            raise
        self._write_llm_call_log(
            stage=stage,
            task=task,
            label=label,
            status="completed",
            started_at=started_at,
            started=started,
            request=payload,
            response=api_response,
            error=None,
        )
        return result

    def _post_with_retries(self, payload: dict[str, Any]) -> LlmApiResponse:
        max_attempts = max(1, self.settings.retryAttempts + 1)
        last_error: ReportEngineError | None = None
        for attempt in range(1, max_attempts + 1):
            try:
                return self._post_once(payload)
            except ReportEngineError as exc:
                last_error = exc
                if not self._is_retriable_error(exc) or attempt == max_attempts:
                    raise
        if last_error is not None:
            raise last_error
        raise ReportEngineError(ErrorCode.CONFIG_INVALID, "LLM request failed", stage="llm")

    def _post_once(self, payload: dict[str, Any]) -> LlmApiResponse:
        session = self.session or requests.Session()
        response: Any | None = None
        try:
            response = session.post(
                self._chat_completions_url(),
                headers={
                    "Authorization": f"Bearer {self.settings.apiKey}",
                    "Content-Type": "application/json",
                },
                json=payload,
                timeout=self.settings.timeoutSeconds,
            )
            status_code = getattr(response, "status_code", 200)
            if status_code == 429 or status_code >= 500:
                raise self._retriable_config_error(self._response_text(response))
            response.raise_for_status()
        except requests.exceptions.Timeout as exc:
            raise ReportEngineError(ErrorCode.LLM_TIMEOUT, "LLM request timed out", stage="llm") from exc
        except requests.exceptions.ConnectionError as exc:
            raise self._retriable_config_error() from exc
        except requests.exceptions.RequestException as exc:
            error = ReportEngineError(ErrorCode.CONFIG_INVALID, "LLM request failed", stage="llm")
            self._attach_raw_response_content(error, self._response_text(response))
            raise error from exc
        finally:
            if self.session is None:
                session.close()

        try:
            data = response.json()
            choice = data["choices"][0]
            content = choice["message"]["content"]
            finish_reason = choice.get("finish_reason")
            usage = data.get("usage")
        except (KeyError, IndexError, TypeError, ValueError) as exc:
            error = ReportEngineError(
                ErrorCode.LLM_INVALID_JSON,
                "LLM response envelope was invalid",
                stage="llm",
            )
            self._attach_raw_response_content(error, self._response_text(response))
            raise error from exc
        if not isinstance(content, str):
            raise ReportEngineError(
                ErrorCode.LLM_INVALID_JSON,
                "LLM response content must be text",
                stage="llm",
            )
        if not content.strip():
            raise ReportEngineError(
                ErrorCode.LLM_INVALID_JSON,
                "LLM response content was empty",
                stage="llm",
            )
        return LlmApiResponse(
            content=content,
            finish_reason=finish_reason if isinstance(finish_reason, str) else None,
            usage=usage if isinstance(usage, dict) else None,
        )

    def _write_llm_call_log(
        self,
        *,
        stage: str,
        task: str,
        label: str,
        status: str,
        started_at: str,
        started: float,
        request: dict[str, Any],
        response: LlmApiResponse | None,
        error: Exception | None,
    ) -> None:
        if self.llm_call_logger is None:
            return
        completed_at = _now_iso()
        duration_ms = max(0, round((time.perf_counter() - started) * 1000))
        self.llm_call_logger.write_call(
            stage=stage,
            task=task,
            label=label,
            status=status,
            started_at=started_at,
            completed_at=completed_at,
            duration_ms=duration_ms,
            request=self._logged_request_payload(request),
            response=self._logged_response_payload(response) or self._logged_error_response_payload(error),
            token_usage=response.usage if response is not None else None,
            error=self._logged_error_payload(error),
        )

    @classmethod
    def _logged_request_payload(cls, payload: dict[str, Any]) -> dict[str, Any]:
        keys = [
            "model",
            "messages",
            "temperature",
            "top_p",
            "top_k",
            "min_p",
            "presence_penalty",
            "repetition_penalty",
            "max_tokens",
            "stream",
            "enable_thinking",
            "separate_reasoning",
            "response_format",
        ]
        logged = {key: payload[key] for key in keys if key in payload}
        if "messages" in logged:
            logged["messages"] = cls._logged_messages(logged["messages"])
        return logged

    @classmethod
    def _logged_messages(cls, messages: Any) -> Any:
        if not isinstance(messages, list):
            return messages
        return [cls._logged_message(message) for message in messages]

    @classmethod
    def _logged_message(cls, message: Any) -> Any:
        if not isinstance(message, dict):
            return message
        logged = dict(message)
        content = logged.get("content")
        if isinstance(content, list):
            logged["content"] = [cls._logged_message_content_item(item) for item in content]
        return logged

    @classmethod
    def _logged_message_content_item(cls, item: Any) -> Any:
        if not isinstance(item, dict):
            return item
        if item.get("type") != "image_url":
            return item
        image_url = item.get("image_url")
        if not isinstance(image_url, dict):
            return item
        logged_image_url = dict(image_url)
        metadata = cls._image_data_url_metadata(logged_image_url.get("url"))
        logged_image_url["url"] = "<image data redacted>"
        logged_image_url.update(metadata)
        return {
            **item,
            "image_url": logged_image_url,
        }

    @staticmethod
    def _image_data_url_metadata(url: Any) -> dict[str, Any]:
        if not isinstance(url, str):
            return {}
        match = re.match(r"^data:([^;,]+);base64,(.*)$", url, flags=re.DOTALL)
        if not match:
            return {}
        encoded = match.group(2)
        metadata: dict[str, Any] = {"mimeType": match.group(1)}
        try:
            metadata["base64Bytes"] = len(base64.b64decode(encoded, validate=True))
        except (binascii.Error, ValueError):
            metadata["base64Chars"] = len(encoded)
        return metadata

    @staticmethod
    def _logged_response_payload(response: LlmApiResponse | None) -> dict[str, Any] | None:
        if response is None:
            return None
        return {
            "content": response.content,
            "finishReason": response.finish_reason,
        }

    @staticmethod
    def _logged_error_response_payload(error: Exception | None) -> dict[str, Any] | None:
        raw_content = getattr(error, "llm_response_content", None)
        if not isinstance(raw_content, str):
            return None
        return {
            "content": raw_content,
            "finishReason": None,
        }

    @staticmethod
    def _logged_error_payload(error: Exception | None) -> dict[str, Any] | None:
        if error is None:
            return None
        return {
            "errorType": type(error).__name__,
            "errorCode": getattr(getattr(error, "code", None), "value", None),
        }

    def _retry_invalid_json(self, call: Callable[[], dict[str, Any]]) -> dict[str, Any]:
        max_attempts = max(1, self.settings.parseRetryAttempts + 1)
        last_error: ReportEngineError | None = None
        for attempt in range(1, max_attempts + 1):
            try:
                return call()
            except ReportEngineError as exc:
                last_error = exc
                if exc.code != ErrorCode.LLM_INVALID_JSON or attempt == max_attempts:
                    raise
        if last_error is not None:
            raise last_error
        raise ReportEngineError(ErrorCode.LLM_INVALID_JSON, "LLM response JSON must be an object", stage="llm")

    @staticmethod
    def _is_retriable_error(exc: ReportEngineError) -> bool:
        return exc.code == ErrorCode.LLM_TIMEOUT or bool(getattr(exc, "retriable", False))

    @staticmethod
    def _retriable_config_error(response_text: str | None = None) -> ReportEngineError:
        error = ReportEngineError(ErrorCode.CONFIG_INVALID, "LLM request failed", stage="llm")
        NovitaLlmAdapter._attach_raw_response_content(error, response_text)
        setattr(error, "retriable", True)
        return error

    @staticmethod
    def _attach_raw_response_content(error: ReportEngineError, response_text: str | None) -> None:
        if isinstance(response_text, str) and response_text:
            setattr(error, "llm_response_content", response_text)

    @staticmethod
    def _response_text(response: Any | None) -> str | None:
        text = getattr(response, "text", None)
        return text if isinstance(text, str) else None

    def _normalize_stage2_component_content(self, content: str) -> Any:
        value = self._parse_stage2_component_content(content)
        for _ in range(5):
            if isinstance(value, dict):
                nested = self._unwrap_stage2_dict(value)
                if nested is value:
                    return value
                value = nested
                continue
            if isinstance(value, str):
                value = self._parse_stage2_component_content(value)
                continue
            if isinstance(value, list):
                html_objects = [item for item in value if isinstance(item, dict) and isinstance(item.get("html"), str)]
                if len(html_objects) == 1:
                    return html_objects[0]
                if len(value) == 1:
                    value = value[0]
                    continue
                return value
            return value
        return value

    def _parse_stage2_component_content(self, content: str) -> Any:
        payload = self._strip_json_fence(content)
        try:
            return json.loads(payload)
        except json.JSONDecodeError:
            starts = sorted(position for position in (payload.find("["), payload.find("{")) if position >= 0)
            for start in starts:
                try:
                    result, _ = json.JSONDecoder().raw_decode(payload[start:])
                    return result
                except json.JSONDecodeError:
                    continue
            raise ReportEngineError(
                ErrorCode.LLM_INVALID_JSON,
                "LLM response content was not valid JSON",
                stage="llm",
            )

    @staticmethod
    def _unwrap_stage2_dict(value: dict[str, Any]) -> Any:
        if "html" in value:
            return value
        for key in ("component", "result", "data", "output"):
            nested = value.get(key)
            if isinstance(nested, (dict, list, str)):
                return nested
        components = value.get("components")
        if isinstance(components, list):
            return components
        return value

    @staticmethod
    def _strip_json_fence(content: str) -> str:
        text = content.strip()
        fenced = re.search(r"```(?:json)?\s*(.*?)\s*```", text, flags=re.IGNORECASE | re.DOTALL)
        if fenced:
            return fenced.group(1).strip()
        return text

    def _chat_completions_url(self) -> str:
        base_url = self.settings.baseUrl.rstrip("/")
        if base_url.endswith("/v1"):
            return f"{base_url}/chat/completions"
        return f"{base_url}/v1/chat/completions"

    @staticmethod
    def _stage3_user_content(prompt_input: dict[str, Any], template_image_data_url: str | None) -> Any:
        text = json.dumps(
            {
                "task": "stage3_layout",
                "promptInput": prompt_input,
            },
            ensure_ascii=False,
        )
        if not template_image_data_url:
            return text
        return [
            {"type": "text", "text": text},
            {"type": "image_url", "image_url": {"url": template_image_data_url}},
        ]

    def _stage5_user_content(
        self,
        report_version: ReportVersion,
        template_context: TemplateContext | None,
    ) -> list[dict[str, Any]]:
        html_path = Path(report_version.htmlPath)
        preview_path = Path(report_version.previewImagePath)
        try:
            report_html = html_path.read_text(encoding="utf-8")
            preview_image = preview_path.read_bytes()
        except OSError as exc:
            raise ReportEngineError(
                ErrorCode.CONFIG_INVALID,
                f"Stage 5 verification input file could not be read: {exc.filename}",
                stage="stage5",
            ) from exc

        text = json.dumps(
            {
                "task": "stage5_verification",
                "reportVersion": {
                    "jobId": report_version.jobId,
                    "version": report_version.version,
                    "htmlPath": report_version.htmlPath,
                    "previewImagePath": report_version.previewImagePath,
                    "status": report_version.status,
                    "createdAt": report_version.createdAt,
                },
                "template": _template_context_payload(template_context),
                "requirements": self.prompt_store.read_json("05_verification_requirements.json"),
                "reportHtml": report_html,
                "responseSchema": {
                    "passed": "boolean",
                    "issues": [
                        {
                            "type": "overlap|overflow|clipping|missing_content|data_mismatch|chart_rendering|footer_overlap|other",
                            "severity": "minor|major|critical",
                            "description": "short issue description",
                            "location": "optional page or element location",
                            "evidence": "optional visual or HTML evidence",
                            "suggestion": "optional concrete fix suggestion",
                        }
                    ],
                    "revisionInstruction": "required when passed is false and a revision should be attempted",
                },
            },
            ensure_ascii=False,
        )
        return [
            {"type": "text", "text": text},
            {
                "label": "generatedPreviewImage",
                "type": "image_url",
                "image_url": {
                    "url": f"data:{self._image_mime_type(preview_path)};base64,{base64.b64encode(preview_image).decode('ascii')}",
                },
            },
            *_template_preview_image_content(template_context),
        ]

    def _normalize_stage5_verification_content(self, content: str) -> dict[str, Any]:
        value = self._parse_stage5_verification_content(content)
        if not isinstance(value, dict):
            raise ReportEngineError(
                ErrorCode.LLM_INVALID_JSON,
                "Stage 5 verification response must be one JSON object",
                stage="llm",
            )
        passed = value.get("passed")
        if not isinstance(passed, bool):
            raise ReportEngineError(
                ErrorCode.LLM_INVALID_JSON,
                "Stage 5 verification response must include boolean passed",
                stage="llm",
            )
        issues = value.get("issues")
        if not isinstance(issues, list):
            raise ReportEngineError(
                ErrorCode.LLM_INVALID_JSON,
                "Stage 5 verification response must include issues as a list",
                stage="llm",
            )
        normalized_issues = [self._normalize_stage5_issue(issue) for issue in issues]
        revision_instruction = value.get("revisionInstruction")
        if revision_instruction is not None and not isinstance(revision_instruction, str):
            raise ReportEngineError(
                ErrorCode.LLM_INVALID_JSON,
                "Stage 5 verification revisionInstruction must be a string",
                stage="llm",
            )

        result: dict[str, Any] = {
            "passed": passed,
            "issues": normalized_issues,
        }
        if isinstance(revision_instruction, str) and revision_instruction.strip():
            result["revisionInstruction"] = revision_instruction.strip()
        return result

    def _parse_stage5_verification_content(self, content: str) -> Any:
        value = self._parse_stage2_component_content(content)
        for _ in range(5):
            if isinstance(value, dict):
                return value
            if isinstance(value, str):
                value = self._parse_stage2_component_content(value)
                continue
            break
        return value

    @staticmethod
    def _normalize_stage5_issue(issue: Any) -> dict[str, Any]:
        if not isinstance(issue, dict):
            raise ReportEngineError(
                ErrorCode.LLM_INVALID_JSON,
                "Stage 5 verification issues must be objects",
                stage="llm",
            )
        required_fields = ("type", "severity", "description")
        missing = [field for field in required_fields if not isinstance(issue.get(field), str) or not issue.get(field).strip()]
        if missing:
            raise ReportEngineError(
                ErrorCode.LLM_INVALID_JSON,
                f"Stage 5 verification issue missing required fields: {', '.join(missing)}",
                stage="llm",
            )
        allowed_types = {
            "overlap",
            "overflow",
            "clipping",
            "missing_content",
            "data_mismatch",
            "chart_rendering",
            "footer_overlap",
            "other",
        }
        issue_type = issue["type"].strip()
        if issue_type not in allowed_types:
            raise ReportEngineError(
                ErrorCode.LLM_INVALID_JSON,
                f"Stage 5 verification issue type is not allowed: {issue_type}",
                stage="llm",
            )

        normalized: dict[str, Any] = {
            "type": issue_type,
            "severity": issue["severity"].strip(),
            "description": issue["description"].strip(),
        }
        for optional_field in ("location", "evidence", "suggestion"):
            value = issue.get(optional_field)
            if isinstance(value, str) and value.strip():
                normalized[optional_field] = value.strip()
        return normalized

    @staticmethod
    def _image_mime_type(path: Path) -> str:
        suffix = path.suffix.lower()
        if suffix in {".jpg", ".jpeg"}:
            return "image/jpeg"
        if suffix == ".webp":
            return "image/webp"
        return "image/png"


def _template_context_payload(template_context: TemplateContext | None) -> dict[str, Any] | None:
    if template_context is None:
        return None
    return {
        "templateId": template_context.templateId,
        "previewImage": template_context.previewImage,
        "page": {
            "size": template_context.page.size,
            "orientation": template_context.page.orientation,
        },
        "name": template_context.name,
    }


def _template_preview_image_content(template_context: TemplateContext | None) -> list[dict[str, Any]]:
    if template_context is None:
        return []
    image_path = _resolve_template_preview_image_path(template_context.previewImage)
    try:
        image_bytes = image_path.read_bytes()
    except OSError as exc:
        raise ReportEngineError(
            ErrorCode.CONFIG_INVALID,
            f"Stage 5 template preview image could not be read: {template_context.previewImage}",
            stage="stage5",
        ) from exc
    return [
        {
            "label": "templatePreviewImage",
            "type": "image_url",
            "image_url": {
                "url": f"data:{NovitaLlmAdapter._image_mime_type(image_path)};base64,{base64.b64encode(image_bytes).decode('ascii')}",
            },
        }
    ]


def _resolve_template_preview_image_path(preview_image: str) -> Path:
    path = Path(preview_image)
    if path.is_file():
        return path
    candidates: list[Path] = []
    if not path.is_absolute():
        candidates.extend(
            [
                Path.cwd() / path,
                Path.cwd().parent / path,
                Path(__file__).resolve().parents[2] / path,
            ]
        )
    for candidate in candidates:
        if candidate.is_file():
            return candidate
    return path


def _now_iso() -> str:
    return datetime.now().astimezone().isoformat(timespec="milliseconds")
