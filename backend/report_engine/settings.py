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
    )


def redact_secret_values(text: str, secrets: list[str]) -> str:
    redacted = text
    for secret in sorted((item for item in secrets if item), key=len, reverse=True):
        redacted = redacted.replace(secret, "<redacted>")
    return redacted
