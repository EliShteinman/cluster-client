from enum import StrEnum
from pathlib import Path

from pydantic import Field, NonNegativeInt, PositiveInt

from app.config.base import FrozenModel, LogLevel


class LogFormat(StrEnum):
    LINE = "line"
    JSON = "json"


class HandlerSettings(FrozenModel):
    enabled: bool
    level: LogLevel
    format: LogFormat


class ConsoleSettings(HandlerSettings):
    enabled: bool = Field(default=True)
    level: LogLevel = Field(default="INFO")
    format: LogFormat = Field(default=LogFormat.LINE)


class FileSettings(HandlerSettings):
    enabled: bool = Field(default=False)
    level: LogLevel = Field(default="DEBUG")
    format: LogFormat = Field(default=LogFormat.JSON)
    path: Path = Field(default=Path("logs/app.log"))
    max_bytes: PositiveInt = Field(default=10 * 1024 * 1024)
    backup_count: NonNegativeInt = Field(default=5)


class FailureFileSettings(FileSettings):
    enabled: bool = Field(default=True)
    level: LogLevel = Field(default="WARNING")
    path: Path = Field(default=Path("logs/failures.log"))
    logger_name: str = Field(default="cluster_client.failures")


class FormattingSettings(FrozenModel):
    line_pattern: str = Field(
        default="%(asctime)s | %(levelname)-8s | %(name)s | trace_id=%(trace_id)s | %(message)s"
    )
    date_format: str = Field(default="%Y-%m-%dT%H:%M:%S%z")


class LoggingSettings(FrozenModel):
    level: LogLevel = Field(default="DEBUG")
    console: ConsoleSettings = Field(default_factory=ConsoleSettings)
    file: FileSettings = Field(default_factory=FileSettings)
    failure_file: FailureFileSettings = Field(default_factory=FailureFileSettings)
    formatting: FormattingSettings = Field(default_factory=FormattingSettings)
