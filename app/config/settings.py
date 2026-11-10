from typing import ClassVar

from pydantic import Field
from pydantic_settings import SettingsConfigDict

from app.config.base import BaseConfig
from app.config.failures import FailureSettings
from app.config.forwarding import ForwardingSettings
from app.config.headers import HeaderSettings
from app.config.logging import LoggingSettings
from app.config.server import ApplicationSettings, ServerSettings
from app.config.telemetry import TelemetrySettings
from app.config.validation import ValidationSettings


class Settings(BaseConfig):
    server: ServerSettings = Field(default_factory=ServerSettings)
    application: ApplicationSettings = Field(default_factory=ApplicationSettings)
    headers: HeaderSettings = Field(default_factory=HeaderSettings)
    validation: ValidationSettings = Field(default_factory=ValidationSettings)
    forwarding: ForwardingSettings = Field(default_factory=ForwardingSettings)
    failures: FailureSettings = Field(default_factory=FailureSettings)
    log: LoggingSettings = Field(default_factory=LoggingSettings)
    telemetry: TelemetrySettings = Field(default_factory=TelemetrySettings)


class NoEnvFileSettings(Settings):
    model_config: ClassVar[SettingsConfigDict] = SettingsConfigDict(env_file=None)
