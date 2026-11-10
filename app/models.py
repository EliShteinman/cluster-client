from enum import StrEnum
from typing import Annotated, ClassVar, Literal

from pydantic import BaseModel, BeforeValidator, ConfigDict, Field, HttpUrl, SecretStr

from app.config.utils import to_upper


class FrozenModel(BaseModel):
    model_config: ClassVar[ConfigDict] = ConfigDict(frozen=True)


class HttpMethod(StrEnum):
    GET = "GET"
    POST = "POST"
    PUT = "PUT"
    PATCH = "PATCH"
    DELETE = "DELETE"


class ClusterRequest(FrozenModel):
    method: Annotated[HttpMethod, BeforeValidator(func=to_upper)]
    url: HttpUrl
    authorization: SecretStr = Field(min_length=1)
    content_type: str | None = Field(default=None)
    passed_through_headers: dict[str, str] = Field(default_factory=dict)
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
