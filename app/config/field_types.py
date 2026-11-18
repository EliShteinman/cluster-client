from typing import Annotated, Literal

from pydantic import BeforeValidator, Field

from app.config.constants import HTTP_TCHAR_PATTERN

MAX_PORT: int = 65535
ERROR_STATUS_CODE_MIN: int = 400
ERROR_STATUS_CODE_MAX: int = 599


def to_upper(value: object) -> object:
    return value.upper() if isinstance(value, str) else value


def to_lower(value: object) -> object:
    return value.lower() if isinstance(value, str) else value


type HeaderName = Annotated[str, Field(pattern=HTTP_TCHAR_PATTERN)]
type LowercaseHeaderName = Annotated[HeaderName, BeforeValidator(func=to_lower)]
type LogLevel = Annotated[
    Literal["CRITICAL", "ERROR", "WARNING", "INFO", "DEBUG"], BeforeValidator(func=to_upper)
]
type ErrorStatusCode = Annotated[int, Field(ge=ERROR_STATUS_CODE_MIN, le=ERROR_STATUS_CODE_MAX)]
type Port = Annotated[int, Field(ge=1, le=MAX_PORT)]
