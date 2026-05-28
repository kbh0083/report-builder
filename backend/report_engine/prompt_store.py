import json
from pathlib import Path
from typing import Any

from .errors import ErrorCode, ReportEngineError


class PromptStore:
    def __init__(self, root: Path | None = None):
        self.root = root or Path(__file__).resolve().parent / "prompt"

    def read_text(self, filename: str) -> str:
        content = "\n".join(
            line
            for line in self._read_raw(filename).splitlines()
            if line.strip() and not line.lstrip().startswith("#")
        )
        if not content.strip():
            raise self._invalid(f"Prompt file is empty: {filename}")
        return content.strip()

    def read_json(self, filename: str) -> Any:
        content = self._strip_json_comments(self._read_raw(filename))
        if not content.strip():
            raise self._invalid(f"Prompt file is empty: {filename}")
        try:
            return json.loads(content)
        except json.JSONDecodeError as exc:
            raise self._invalid(f"Prompt JSON file is invalid: {filename}") from exc

    def _read_raw(self, filename: str) -> str:
        path = self._path(filename)
        try:
            content = path.read_text(encoding="utf-8")
        except OSError as exc:
            raise self._invalid(f"Prompt file could not be read: {filename}") from exc
        return content

    def _path(self, filename: str) -> Path:
        if Path(filename).name != filename:
            raise self._invalid(f"Prompt filename must be flat: {filename}")
        return self.root / filename

    @staticmethod
    def _invalid(detail: str) -> ReportEngineError:
        return ReportEngineError(ErrorCode.CONFIG_INVALID, detail, stage="prompt")

    @staticmethod
    def _strip_json_comments(content: str) -> str:
        result: list[str] = []
        in_string = False
        escape_next = False
        in_line_comment = False
        in_block_comment = False
        index = 0
        while index < len(content):
            char = content[index]
            next_char = content[index + 1] if index + 1 < len(content) else ""

            if in_line_comment:
                if char in "\r\n":
                    in_line_comment = False
                    result.append(char)
                index += 1
                continue

            if in_block_comment:
                if char == "*" and next_char == "/":
                    in_block_comment = False
                    index += 2
                else:
                    if char in "\r\n":
                        result.append(char)
                    index += 1
                continue

            if in_string:
                result.append(char)
                if escape_next:
                    escape_next = False
                elif char == "\\":
                    escape_next = True
                elif char == '"':
                    in_string = False
                index += 1
                continue

            if char == '"':
                in_string = True
                result.append(char)
                index += 1
                continue

            if char == "/" and next_char == "/":
                in_line_comment = True
                index += 2
                continue

            if char == "/" and next_char == "*":
                in_block_comment = True
                index += 2
                continue

            result.append(char)
            index += 1

        return "".join(result)
