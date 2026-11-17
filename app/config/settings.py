from typing import ClassVar, Self

from pydantic import Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

from app.config.access import AccessSettings
from app.config.application import ApplicationSettings
from app.config.failures import FailureSettings
from app.config.forwarding import ForwardingSettings
from app.config.headers import HeaderSettings
from app.config.logging import LoggingSettings
from app.config.server import ServerSettings
from app.config.telemetry import TelemetrySettings
from app.config.validation import ValidationSettings

ENV_FILE: str = ".env"
ENV_PREFIX: str = "CLUSTER_CLIENT_"
ENV_NESTED_DELIMITER: str = "__"


class Settings(BaseSettings):
    model_config: ClassVar[SettingsConfigDict] = SettingsConfigDict(
        env_file=ENV_FILE,
        env_prefix=ENV_PREFIX,
        env_nested_delimiter=ENV_NESTED_DELIMITER,
        nested_model_default_partial_update=True,
        extra="ignore",
        frozen=True,
    )

    server: ServerSettings = Field(default=ServerSettings())
    application: ApplicationSettings = Field(default=ApplicationSettings())
    access: AccessSettings
    headers: HeaderSettings = Field(default=HeaderSettings())
    validation: ValidationSettings = Field(default=ValidationSettings())
    forwarding: ForwardingSettings = Field(default=ForwardingSettings())
    failures: FailureSettings = Field(default=FailureSettings())
    log: LoggingSettings = Field(default=LoggingSettings())
    telemetry: TelemetrySettings = Field(default=TelemetrySettings())

    @model_validator(mode="after")
    def own_headers_keep_their_prefixes(self) -> Self:
        target_prefix: str = self.headers.target_prefix
        edge_prefix: str = self.forwarding.edge_header_prefix
        read_headers: list[str] = [self.headers.method, self.headers.url, self.access.header]
        written_headers: list[str] = [self.failures.error_header, self.failures.target_status_header]
        forwarded: list[str] = [name for name in read_headers if name.startswith(target_prefix)]
        fakeable: list[str] = [name for name in written_headers if not name.lower().startswith(edge_prefix)]
        problems: list[str] = [
            *(f"{name} must not start with {target_prefix}" for name in forwarded),
            *(f"{name} must start with {edge_prefix}" for name in fakeable),
        ]
        if problems:
            raise ValueError("; ".join(problems))
        return self


class NoEnvFileSettings(Settings):
    model_config: ClassVar[SettingsConfigDict] = SettingsConfigDict(env_file=None)
