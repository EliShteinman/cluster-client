from typing import ClassVar

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

from app.config.access import AccessSettings
from app.config.constants import ENV_FILE, ENV_NESTED_DELIMITER, ENV_PREFIX
from app.config.failures import FailureSettings
from app.config.forwarding import ForwardingSettings
from app.config.headers import HeaderSettings
from app.config.logging import LoggingSettings
from app.config.server import ApplicationSettings, ServerSettings
from app.config.telemetry import TelemetrySettings
from app.config.validation import ValidationSettings


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


class NoEnvFileSettings(Settings):
    model_config: ClassVar[SettingsConfigDict] = SettingsConfigDict(env_file=None)
