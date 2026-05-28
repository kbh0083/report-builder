import json
import re
from dataclasses import asdict, is_dataclass
from pathlib import Path
from typing import Any

from .settings import redact_secret_values


SENSITIVE_KEYS = {
    "api_key",
    "apikey",
    "authorization",
    "llm_api_key",
    "password",
    "refresh_token",
    "secret",
    "token",
    "access_token",
}


class ArtifactLogger:
    def __init__(self, log_root: str | Path, job_id: str, secrets: list[str] | None = None):
        job_path = Path(job_id)
        if job_path.is_absolute() or ".." in job_path.parts or len(job_path.parts) != 1:
            raise ValueError(f"Log job id must be a single safe path segment: {job_id}")
        self.log_root = Path(log_root)
        self.job_id = job_id
        self.job_dir = self.log_root / job_id
        self.secrets = [secret for secret in (secrets or []) if secret]

    def write_json(self, relative_path: str | Path, data: Any) -> Path:
        path = self._resolve(relative_path)
        payload = self._redact(data)
        text = json.dumps(payload, ensure_ascii=False, indent=2) + "\n"
        path.write_text(text, encoding="utf-8")
        return path

    def append_json_line(self, relative_path: str | Path, data: Any) -> Path:
        path = self._resolve(relative_path)
        payload = self._redact(data)
        text = json.dumps(payload, ensure_ascii=False, separators=(",", ":")) + "\n"
        with path.open("a", encoding="utf-8") as file:
            file.write(text)
        return path

    def write_text(self, relative_path: str | Path, text: str) -> Path:
        path = self._resolve(relative_path)
        path.write_text(redact_secret_values(text, self.secrets), encoding="utf-8")
        return path

    def write_html(self, relative_path: str | Path, html: str) -> Path:
        return self.write_text(relative_path, html)

    def _resolve(self, relative_path: str | Path) -> Path:
        relative = Path(relative_path)
        if relative.is_absolute() or ".." in relative.parts:
            raise ValueError(f"Log artifact path must be relative to job directory: {relative_path}")
        path = self.job_dir / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        return path

    def _redact(self, value: Any) -> Any:
        if is_dataclass(value) and not isinstance(value, type):
            return self._redact(asdict(value))
        if isinstance(value, dict):
            redacted: dict[Any, Any] = {}
            for key, item in value.items():
                if self._is_sensitive_key(str(key)):
                    redacted[key] = "<redacted>"
                else:
                    redacted[key] = self._redact(item)
            return redacted
        if isinstance(value, list):
            return [self._redact(item) for item in value]
        if isinstance(value, tuple):
            return [self._redact(item) for item in value]
        if isinstance(value, str):
            return redact_secret_values(value, self.secrets)
        return value

    @staticmethod
    def _is_sensitive_key(key: str) -> bool:
        normalized = _normalize_key(key)
        if normalized in SENSITIVE_KEYS:
            return True
        if normalized in {"api_key", "private_key", "secret_key"}:
            return True
        if normalized.endswith("_api_key"):
            return True
        if normalized.endswith("_token") and normalized != "token_usage":
            return True
        parts = normalized.split("_")
        return "secret" in parts or "password" in parts


def _normalize_key(key: str) -> str:
    with_word_boundaries = re.sub(r"(?<=[a-z0-9])(?=[A-Z])", "_", key.strip())
    normalized = with_word_boundaries.lower().replace("-", "_")
    return re.sub(r"_+", "_", normalized)
