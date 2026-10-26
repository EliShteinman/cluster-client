from typing import ClassVar

from pydantic import Field
from pydantic_settings import SettingsConfigDict

from app.config.base import ENV_PREFIX, EnvironmentSettings
from app.config.failures import FailureSettings
from app.config.forwarding import ForwardingSettings
from app.config.logging import LoggingSettings
from app.config.server import ApplicationSettings, ServerSettings
from app.config.tracing import TracingSettings
from app.config.validation import ValidationSettings


class Settings(EnvironmentSettings):
    model_config: ClassVar[SettingsConfigDict] = SettingsConfigDict(env_prefix=ENV_PREFIX)

    server: ServerSettings = Field(default_factory=ServerSettings)
    application: ApplicationSettings = Field(default_factory=ApplicationSettings)
    validation: ValidationSettings = Field(default_factory=ValidationSettings)
    forwarding: ForwardingSettings = Field(default_factory=ForwardingSettings)
    failures: FailureSettings = Field(default_factory=FailureSettings)
    log: LoggingSettings = Field(default_factory=LoggingSettings)
    tracing: TracingSettings = Field(default_factory=TracingSettings)
