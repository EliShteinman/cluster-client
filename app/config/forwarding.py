from pydantic import Field, PositiveFloat

from app.config.base import FrozenModel, HeaderName, LowercaseHeaderName


class ForwardingSettings(FrozenModel):
    connect_timeout_seconds: PositiveFloat = Field(default=5.0)
    timeout_seconds: PositiveFloat = Field(default=28.0)
    authorization_header: HeaderName = Field(default="authorization")
    content_type_header: HeaderName = Field(default="content-type")
    passed_through_request_headers: frozenset[LowercaseHeaderName] = Field(
        default=frozenset({"cluster-state-id", "x-task-id", "x-result-ttl"})
    )
    recomputed_response_headers: frozenset[LowercaseHeaderName] = Field(
        default=frozenset({"content-length", "content-encoding", "transfer-encoding", "connection"})
    )
