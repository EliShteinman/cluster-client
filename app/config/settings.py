from enum import StrEnum
from importlib.metadata import version
from pathlib import Path
from typing import Annotated, ClassVar, Literal

from pydantic import BaseModel, BeforeValidator, ConfigDict, Field, NonNegativeInt, PositiveFloat, PositiveInt
from pydantic_settings import BaseSettings, SettingsConfigDict

DISTRIBUTION_NAME: str = "cluster-client"
TEXT_ENCODING: str = "utf-8"
HTTP_HEADER_NAME_PATTERN: str = r"^[A-Za-z0-9!#$%&'*+.^_`|~-]+$"
MAX_PORT: int = 65535
ERROR_STATUS_CODE_MIN: int = 400
ERROR_STATUS_CODE_MAX: int = 599


def to_upper(value: object) -> object:
    return value.upper() if isinstance(value, str) else value


type HeaderName = Annotated[str, Field(pattern=HTTP_HEADER_NAME_PATTERN)]
type LogLevel = Annotated[
    Literal["CRITICAL", "ERROR", "WARNING", "INFO", "DEBUG"], BeforeValidator(func=to_upper)
]
type ErrorStatusCode = Annotated[int, Field(ge=ERROR_STATUS_CODE_MIN, le=ERROR_STATUS_CODE_MAX)]


class FrozenModel(BaseModel):
    model_config: ClassVar[ConfigDict] = ConfigDict(frozen=True)


class ServerSettings(FrozenModel):
    host: str = Field(default="127.0.0.1")
    port: int = Field(default=8000, ge=1, le=MAX_PORT)
    server_header: bool = Field(default=False)
    date_header: bool = Field(default=False)


class ApplicationSettings(FrozenModel):
    title: str = Field(default=DISTRIBUTION_NAME)
    version: str = Field(default_factory=lambda: version(distribution_name=DISTRIBUTION_NAME))


class HeaderSettings(BaseSettings):
    model_config: ClassVar[SettingsConfigDict] = SettingsConfigDict(
        env_prefix="CLUSTER_CLIENT_HEADERS__", env_file=".env", extra="ignore", frozen=True
    )

    method: HeaderName = Field(default="x-cluster-method")
    url: HeaderName = Field(default="x-cluster-url")
    authorization: HeaderName = Field(default="x-cluster-authorization")
    content_type: HeaderName = Field(default="content-type")


class ForwardingSettings(FrozenModel):
    timeout_seconds: PositiveFloat = Field(default=30.0)
    authorization_header: HeaderName = Field(default="authorization")
    content_type_header: HeaderName = Field(default="content-type")
    passed_through_request_headers: frozenset[HeaderName] = Field(
        default=frozenset({"cluster-state-id", "x-task-id", "x-result-ttl"})
    )
    recomputed_response_headers: frozenset[HeaderName] = Field(
        default=frozenset({"content-length", "content-encoding", "transfer-encoding", "connection"})
    )


class ValidationSettings(FrozenModel):
    schema_path: Path = Field(default=Path("config/response-schema.json"))
    ignored_fields_path: Path = Field(default=Path("config/ignored-fields.json"))


class FailureCode(FrozenModel):
    status_code: ErrorStatusCode
    error_code: str


class FailureSettings(FrozenModel):
    invalid_request: FailureCode = Field(default=FailureCode(status_code=400, error_code="invalid_request"))
    rejected: FailureCode = Field(default=FailureCode(status_code=502, error_code="response_rejected"))
    connection_failed: FailureCode = Field(
        default=FailureCode(status_code=502, error_code="connection_failed")
    )
    no_response: FailureCode = Field(default=FailureCode(status_code=504, error_code="timeout"))
    error_header: HeaderName = Field(default="x-edge-error")
    cluster_status_header: HeaderName = Field(default="x-edge-cluster-status")
    content_type: str = Field(default="application/json")


class LogFormat(StrEnum):
    LINE = "line"
    JSON = "json"


class ConsoleSettings(FrozenModel):
    enabled: bool = Field(default=True)
    level: LogLevel = Field(default="INFO")
    format: LogFormat = Field(default=LogFormat.LINE)


class FileSettings(FrozenModel):
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
    redacted_fields_path: Path = Field(default=Path("config/redacted-fields.json"))
    logger_name: str = Field(default="cluster_client.failures")


class FormattingSettings(FrozenModel):
    line_pattern: str = Field(
        default="%(asctime)s | %(levelname)-8s | %(name)s | trace_id=%(trace_id)s | %(message)s"
    )
    date_format: str = Field(default="%Y-%m-%dT%H:%M:%S%z")


class TracingSettings(FrozenModel):
    traceparent_header: HeaderName = Field(default="traceparent")


class LoggingSettings(FrozenModel):
    level: LogLevel = Field(default="DEBUG")
    console: ConsoleSettings = Field(default_factory=ConsoleSettings)
    file: FileSettings = Field(default_factory=FileSettings)
    failure_file: FailureFileSettings = Field(default_factory=FailureFileSettings)
    formatting: FormattingSettings = Field(default_factory=FormattingSettings)
    tracing: TracingSettings = Field(default_factory=TracingSettings)


class Settings(BaseSettings):
    model_config: ClassVar[SettingsConfigDict] = SettingsConfigDict(
        env_prefix="CLUSTER_CLIENT_",
        env_nested_delimiter="__",
        env_file=".env",
        extra="ignore",
        frozen=True,
    )

    server: ServerSettings = Field(default_factory=ServerSettings)
    application: ApplicationSettings = Field(default_factory=ApplicationSettings)
    validation: ValidationSettings = Field(default_factory=ValidationSettings)
    forwarding: ForwardingSettings = Field(default_factory=ForwardingSettings)
    failures: FailureSettings = Field(default_factory=FailureSettings)
    log: LoggingSettings = Field(default_factory=LoggingSettings)
