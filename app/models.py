from typing import Annotated, ClassVar, Literal

from pydantic import AfterValidator, AnyHttpUrl, BaseModel, ConfigDict, Field, TypeAdapter

from app.config.constants import HTTP_TCHAR_PATTERN
from app.logger.decorators import log_debug

HTTP_URL: TypeAdapter[AnyHttpUrl] = TypeAdapter(type=AnyHttpUrl)


class FrozenModel(BaseModel):
    model_config: ClassVar[ConfigDict] = ConfigDict(frozen=True)


@log_debug
def checked_http_url(url: str) -> str:
    HTTP_URL.validate_python(url)
    return url


class TargetRequest(FrozenModel):
    method: str = Field(
        pattern=HTTP_TCHAR_PATTERN, description="Any HTTP method; sent as requests sends it, in upper case"
    )
    url: Annotated[str, AfterValidator(func=checked_http_url)] = Field(
        description="An http or https URL of any length; sent as requests sends it, query included"
    )
    headers: dict[str, str] = Field(default_factory=dict, repr=False)
    body: bytes = Field(default=b"")


class Answer(FrozenModel):
    status_code: int
    headers: dict[str, str] = Field(default_factory=dict)
    content: bytes = Field(default=b"")


class FailureBody(FrozenModel):
    error: str = Field(description="The configured error code, the same as the x-edge-error header")
    rule: str | None = Field(
        default=None, description="The JSON Schema keyword that failed, or the not-JSON rule; rejections only"
    )
    field: str | None = Field(
        default=None, description="The failing field; a long path is cut from the start and begins with ..."
    )
    reason: list[str] = Field(
        description="The whole explanation in parts that each fit the firewall; joined, they are the text"
    )


class FailureDetails(FrozenModel):
    error: str
    rule: str | None = None
    field: str | None = None
    reason: str


class FailureRecord(FailureDetails):
    method: str
    url: str
    target_status_code: int | None = None
    target_response: str | None = None


class ErrorBodyLimits(FrozenModel):
    error_length: int
    rule_length: int
    field_length: int
    part_length: int
    max_parts: int


class HealthStatus(FrozenModel):
    status: Literal["up"] = Field(default="up")
