import json
from collections.abc import Callable
from pathlib import Path

from pydantic import JsonValue

from app.config import ConsoleSettings, FailureFileSettings, FileSettings, LogFormat, LoggingSettings

type JsonLines = Callable[[], list[dict[str, JsonValue]]]


def json_file_settings(*, log_path: Path, failure_log_path: Path) -> LoggingSettings:
    return LoggingSettings(
        console=ConsoleSettings(enabled=False),
        file=FileSettings(enabled=True, path=log_path, format=LogFormat.JSON),
        failure_file=FailureFileSettings(path=failure_log_path),
    )


def read_json_lines(*, log_path: Path) -> list[dict[str, JsonValue]]:
    if not log_path.exists():
        return []
    return [json.loads(s=line) for line in log_path.read_text(encoding="utf-8").splitlines() if line]
