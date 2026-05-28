import re
from threading import Lock
from typing import Any

from .artifact_logger import ArtifactLogger


class LlmCallLogger:
    def __init__(self, artifact_logger: ArtifactLogger):
        self.artifact_logger = artifact_logger
        self._lock = Lock()
        self._sequence = 0

    def write_call(
        self,
        *,
        stage: str,
        task: str,
        label: str,
        status: str,
        started_at: str,
        completed_at: str,
        duration_ms: int,
        request: dict[str, Any],
        response: dict[str, Any] | None,
        token_usage: dict[str, Any] | None,
        error: dict[str, Any] | None,
    ) -> None:
        with self._lock:
            self._sequence += 1
            sequence = self._sequence
        payload = {
            "stage": stage,
            "task": task,
            "callId": f"llm_{sequence:04d}",
            "status": status,
            "startedAt": started_at,
            "completedAt": completed_at,
            "durationMs": duration_ms,
            "request": request,
            "response": response,
            "tokenUsage": token_usage,
            "error": error,
        }
        filename = f"{sequence:04d}_{_safe_segment(task)}_{_safe_segment(label)}.json"
        self.artifact_logger.write_json(f"{stage}/llm_calls/{filename}", payload)


def _safe_segment(value: str) -> str:
    cleaned = re.sub(r"[^A-Za-z0-9_.-]+", "_", value.strip())
    cleaned = cleaned.strip("._-")
    return cleaned or "call"
