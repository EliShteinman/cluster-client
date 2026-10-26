from typing import ClassVar

from pydantic import Field
from pydantic_settings import SettingsConfigDict

from app.config.base import ENV_NESTED_DELIMITER, ENV_PREFIX, EnvironmentSettings, HeaderName

HEADERS_ENV_PREFIX: str = f"{ENV_PREFIX}HEADERS{ENV_NESTED_DELIMITER}"


class HeaderSettings(EnvironmentSettings):
    model_config: ClassVar[SettingsConfigDict] = SettingsConfigDict(env_prefix=HEADERS_ENV_PREFIX)

    method: HeaderName = Field(default="x-cluster-method")
    url: HeaderName = Field(default="x-cluster-url")
    authorization: HeaderName = Field(default="x-cluster-authorization")
    content_type: HeaderName = Field(default="content-type")
