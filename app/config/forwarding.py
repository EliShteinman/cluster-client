from pydantic import Field, PositiveFloat

from app.config.base import FrozenModel, HeaderName


class ForwardingSettings(FrozenModel):
    timeout_seconds: PositiveFloat = Field(default=30.0)
    authorization_header: HeaderName = Field(default="authorization")
    content_type_header: HeaderName = Field(default="content-type")
    passed_through_request_headers: frozenset[HeaderName] = Field(
        default=frozenset({"cluster-state-id", "x-task-id", "x-result-ttl"})
    )
    recomputed_response_headers: frozenset[HeaderName] = Field(
        default=frozenset({"content-length", "content-encoding", "transfer-encoding", "connection"})
    )
