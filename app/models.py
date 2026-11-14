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


class RequestFailure(FailureDetails):
    method: HttpMethod
    url: str
    cluster_status_code: int | None = None
    cluster_response: str | None = None


class HealthStatus(FrozenModel):
    status: Literal["up"] = Field(default="up")
