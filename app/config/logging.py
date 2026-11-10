from enum import StrEnum
from pathlib import Path

from pydantic import Field, NonNegativeInt, PositiveInt

from app.config.base import BaseConfig
from app.config.field_types import LogLevel


class LogFormat(StrEnum):
    LINE = "line"
    JSON = "json"


class HandlerSettings(BaseConfig):
    enabled: bool
    level: LogLevel
    format: LogFormat


class FileSettings(HandlerSettings):
    path: Path
    max_bytes: PositiveInt
    backup_count: NonNegativeInt


class FailureFileSettings(FileSettings):
    logger_name: str


class FormattingSettings(BaseConfig):
    line_pattern: str = Field(
        default="%(asctime)s | %(levelname)-8s | %(name)s | trace_id=%(otelTraceID)s | %(message)s"
    )
    date_format: str = Field(default="%Y-%m-%dT%H:%M:%S%z")


class LoggingSettings(BaseConfig):
    level: LogLevel = Field(default="DEBUG")
    console: HandlerSettings = Field(
        default=HandlerSettings(enabled=True, level="INFO", format=LogFormat.LINE)
    )
    file: FileSettings = Field(
        default=FileSettings(
            enabled=False,
            level="DEBUG",
            format=LogFormat.JSON,
            path=Path("logs/app.log"),
            max_bytes=10 * 1024 * 1024,
            backup_count=5,
        )
    )
    failure_file: FailureFileSettings = Field(
        default=FailureFileSettings(
            enabled=True,
            level="WARNING",
            format=LogFormat.JSON,
            path=Path("logs/failures.log"),
            max_bytes=10 * 1024 * 1024,
            backup_count=5,
            logger_name="cluster_client.failures",
        )
    )
    formatting: FormattingSettings = Field(default_factory=FormattingSettings)
