import os
from dataclasses import dataclass
from pathlib import Path

from .errors import ErrorCode, ReportEngineError


@dataclass(frozen=True)
class LlmSettings:
    model: str
    baseUrl: str
    apiKey: str
    temperature: float
    maxTokens: int
    timeoutSeconds: int
    chunkSizeChars: int
    stageBatchSize: int
    topP: float = 1.0
    topK: int = 20
    minP: float = 0.0
    presencePenalty: float = 0.0
    repetitionPenalty: float = 1.0
    retryAttempts: int = 3
    parseRetryAttempts: int = 3
    enableThinking: bool = False
    separateReasoning: bool = True


def parse_env_file(path: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    if not path.exists():
        return values
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        values[key.strip()] = value.strip().strip('"').strip("'")
    return values


def load_llm_settings(env_path: Path) -> LlmSettings:
    values = parse_env_file(env_path)
    values.update({key: value for key, value in os.environ.items() if key.startswith("LLM_")})
    required = [
        "LLM_MODEL",
        "LLM_BASE_URL",
        "LLM_API_KEY",
        "LLM_TEMPERATURE",
        "LLM_MAX_TOKENS",
        "LLM_TIMEOUT_SECONDS",
        "LLM_CHUNK_SIZE_CHARS",
        "LLM_STAGE_BATCH_SIZE",
    ]
    missing = [key for key in required if not values.get(key)]
    if missing:
        raise ReportEngineError(
            ErrorCode.CONFIG_INVALID,
            f"Missing required LLM settings: {', '.join(missing)}",
            stage="settings",
        )
    return LlmSettings(
        model=values["LLM_MODEL"],
        baseUrl=values["LLM_BASE_URL"],
        apiKey=values["LLM_API_KEY"],
        temperature=float(values["LLM_TEMPERATURE"]),
        maxTokens=int(values["LLM_MAX_TOKENS"]),
        timeoutSeconds=int(values["LLM_TIMEOUT_SECONDS"]),
        chunkSizeChars=int(values["LLM_CHUNK_SIZE_CHARS"]),
        stageBatchSize=int(values["LLM_STAGE_BATCH_SIZE"]),
        topP=float(values.get("LLM_TOP_P", "1.0")),
        topK=int(values.get("LLM_TOP_K", "20")),
        minP=float(values.get("LLM_MIN_P", "0.0")),
        presencePenalty=float(values.get("LLM_PRESENCE_PENALTY", "0.0")),
        repetitionPenalty=float(values.get("LLM_REPETITION_PENALTY", "1.0")),
        retryAttempts=int(values.get("LLM_RETRY_ATTEMPTS", "3")),
        parseRetryAttempts=int(values.get("LLM_PARSE_RETRY_ATTEMPTS", "3")),
        enableThinking=_parse_bool(values.get("LLM_ENABLE_THINKING", "false")),
        separateReasoning=_parse_bool(values.get("LLM_SEPARATE_REASONING", "true")),
    )


def redact_secret_values(text: str, secrets: list[str]) -> str:
    redacted = text
    for secret in sorted((item for item in secrets if item), key=len, reverse=True):
        redacted = redacted.replace(secret, "<redacted>")
    return redacted


def _parse_bool(value: str) -> bool:
    return value.strip().lower() in {"1", "true", "yes", "on"}
