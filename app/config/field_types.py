from typing import Annotated, Literal

from pydantic import BeforeValidator, Field

from app.config.constants import (
    ERROR_STATUS_CODE_MAX,
    ERROR_STATUS_CODE_MIN,
    HTTP_HEADER_NAME_PATTERN,
    MAX_PORT,
)
from app.config.utils import to_lower, to_upper

type HeaderName = Annotated[str, Field(pattern=HTTP_HEADER_NAME_PATTERN)]
type LowercaseHeaderName = Annotated[HeaderName, BeforeValidator(func=to_lower)]
type LogLevel = Annotated[
    Literal["CRITICAL", "ERROR", "WARNING", "INFO", "DEBUG"], BeforeValidator(func=to_upper)
]
type ErrorStatusCode = Annotated[int, Field(ge=ERROR_STATUS_CODE_MIN, le=ERROR_STATUS_CODE_MAX)]
type Port = Annotated[int, Field(ge=1, le=MAX_PORT)]
