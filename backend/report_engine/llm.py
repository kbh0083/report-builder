import json
import re
from collections.abc import Callable
from typing import Any, Protocol

import requests

from .errors import ErrorCode, ReportEngineError
from .settings import LlmSettings


class LlmAdapter(Protocol):
    def generate_stage2_component(self, component_source: dict[str, Any]) -> dict[str, Any]:
        """Return the LLM-generated Stage 2 fields for one component source."""

    def generate_stage3_layout(self, prompt_input: dict[str, Any]) -> str:
        """Return a single HTML report draft for Stage 3."""


class NovitaLlmAdapter:
    def __init__(self, settings: LlmSettings, session: Any | None = None):
        self.settings = settings
        self.session = session

    def generate_stage2_component(self, component_source: dict[str, Any]) -> dict[str, Any]:
        def generate() -> dict[str, Any]:
            content = self._post_chat(
                [
                    {
                        "role": "system",
                        "content": (
                            "Generate one unstyled ETF report HTML fragment. "
                            "Return raw JSON only as a single JSON object with keys html, chartSpec, and styled. "
                            "Do not return an array, Markdown fences, or explanatory text. "
                            "Do not return reasoning-only or empty content. "
                            "The html value must include the exact supplied data-component-id and must not include style, class, or style tags. "
                            "Set chartSpec to an object only for performance_chart; otherwise set chartSpec to null."
                        ),
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
            )
            result = self._normalize_stage2_component_content(content)
            if not isinstance(result, dict):
                raise ReportEngineError(
                    ErrorCode.LLM_INVALID_JSON,
                    "LLM response JSON must be an object",
                    stage="llm",
                )
            return result

        return self._retry_invalid_json(generate)

    def generate_stage3_layout(self, prompt_input: dict[str, Any]) -> str:
        return self._post_chat(
            [
                {
                    "role": "system",
                    "content": (
                        "Generate a single complete A4 portrait HTML document. "
                        "Return raw HTML only and start exactly with <!doctype html>. "
                        "Do not wrap the answer in Markdown fences or add explanations. "
                        "Do not render charts in this stage; preserve data-chart-placeholder containers only. "
                        "Do not create SVG, canvas, script, Chart.js, or other chart rendering markup. "
                        "Keep footer and bottom disclaimers in normal document flow; never use position:absolute or position:fixed for them. "
                        "Reserve a bottom safe area so the final section never overlaps footer text. "
                        "Preserve every supplied Stage 2 component id and do not change source values."
                    ),
                },
                {
                    "role": "user",
                    "content": json.dumps(
                        {
                            "task": "stage3_layout",
                            "promptInput": prompt_input,
                        },
                        ensure_ascii=False,
                    ),
                },
            ],
            response_format=None,
        ).strip()

    def _post_chat(self, messages: list[dict[str, str]], response_format: dict[str, str] | None) -> str:
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

        return self._post_with_retries(payload)

    def _post_with_retries(self, payload: dict[str, Any]) -> str:
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

    def _post_once(self, payload: dict[str, Any]) -> str:
        session = self.session or requests.Session()
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
                raise self._retriable_config_error()
            response.raise_for_status()
        except requests.exceptions.Timeout as exc:
            raise ReportEngineError(ErrorCode.LLM_TIMEOUT, "LLM request timed out", stage="llm") from exc
        except requests.exceptions.ConnectionError as exc:
            raise self._retriable_config_error() from exc
        except requests.exceptions.RequestException as exc:
            raise ReportEngineError(ErrorCode.CONFIG_INVALID, "LLM request failed", stage="llm") from exc
        finally:
            if self.session is None:
                session.close()

        try:
            data = response.json()
            content = data["choices"][0]["message"]["content"]
        except (KeyError, IndexError, TypeError, ValueError) as exc:
            raise ReportEngineError(
                ErrorCode.LLM_INVALID_JSON,
                "LLM response envelope was invalid",
                stage="llm",
            ) from exc
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
        return content

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
    def _retriable_config_error() -> ReportEngineError:
        error = ReportEngineError(ErrorCode.CONFIG_INVALID, "LLM request failed", stage="llm")
        setattr(error, "retriable", True)
        return error

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
