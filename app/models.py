from enum import StrEnum
from typing import Annotated, ClassVar, Literal

from pydantic import BeforeValidator, ConfigDict, Field, HttpUrl, SecretStr

from app.config import FrozenModel, HeaderSettings, to_upper

HEADER_NAMES: HeaderSettings = HeaderSettings()


class HttpMethod(StrEnum):
    GET = "GET"
    POST = "POST"
    PUT = "PUT"
    PATCH = "PATCH"
    DELETE = "DELETE"


class ClusterRequest(FrozenModel):
    model_config: ClassVar[ConfigDict] = ConfigDict(validate_by_alias=True, validate_by_name=True)

    method: Annotated[HttpMethod, BeforeValidator(func=to_upper)] = Field(
        validation_alias=HEADER_NAMES.method.lower()
    )
    url: HttpUrl = Field(validation_alias=HEADER_NAMES.url.lower())
    authorization: SecretStr = Field(min_length=1, validation_alias=HEADER_NAMES.authorization.lower())
    content_type: str | None = Field(default=None, validation_alias=HEADER_NAMES.content_type.lower())
    body: bytes = Field(default=b"")


class ClusterResponse(FrozenModel):
    status_code: int
    headers: dict[str, str] = Field(default_factory=dict)
    content: bytes = Field(default=b"")


class FailureBody(FrozenModel):
    error: str
    reason: str
    field: str | None = None


class RequestFailure(FailureBody):
    method: HttpMethod
    url: str
    cluster_status_code: int | None = None
    cluster_response: str | None = None


class HealthStatus(FrozenModel):
    status: Literal["up"] = Field(default="up")
