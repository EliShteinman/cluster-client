from typing import ClassVar

from pydantic_settings import BaseSettings, SettingsConfigDict

from app.config.constants import ENV_FILE, ENV_NESTED_DELIMITER, ENV_PREFIX


class BaseConfig(BaseSettings):
    model_config: ClassVar[SettingsConfigDict] = SettingsConfigDict(
        env_file=ENV_FILE,
        env_prefix=ENV_PREFIX,
        env_nested_delimiter=ENV_NESTED_DELIMITER,
        nested_model_default_partial_update=True,
        extra="ignore",
        frozen=True,
    )
