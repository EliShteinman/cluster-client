from typing import Annotated, ClassVar, Literal

from pydantic import BaseModel, BeforeValidator, ConfigDict, Field
from pydantic_settings import BaseSettings, SettingsConfigDict

TEXT_ENCODING: str = "utf-8"
ENV_FILE: str = ".env"
ENV_PREFIX: str = "CLUSTER_CLIENT_"
ENV_NESTED_DELIMITER: str = "__"
HTTP_HEADER_NAME_PATTERN: str = r"^[A-Za-z0-9!#$%&'*+.^_`|~-]+$"
ERROR_STATUS_CODE_MIN: int = 400
ERROR_STATUS_CODE_MAX: int = 599


def to_upper(value: object) -> object:
    return value.upper() if isinstance(value, str) else value


def to_lower(value: object) -> object:
    return value.lower() if isinstance(value, str) else value


type HeaderName = Annotated[str, Field(pattern=HTTP_HEADER_NAME_PATTERN)]
type LowercaseHeaderName = Annotated[HeaderName, BeforeValidator(func=to_lower)]
type LogLevel = Annotated[
    Literal["CRITICAL", "ERROR", "WARNING", "INFO", "DEBUG"], BeforeValidator(func=to_upper)
]
type ErrorStatusCode = Annotated[int, Field(ge=ERROR_STATUS_CODE_MIN, le=ERROR_STATUS_CODE_MAX)]


class FrozenModel(BaseModel):
    model_config: ClassVar[ConfigDict] = ConfigDict(frozen=True)


class EnvironmentSettings(BaseSettings):
    model_config: ClassVar[SettingsConfigDict] = SettingsConfigDict(
        env_file=ENV_FILE, env_nested_delimiter=ENV_NESTED_DELIMITER, extra="ignore", frozen=True
    )
