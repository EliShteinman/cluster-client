from typing import Self

from pydantic import Field, PositiveFloat, model_validator

from app.config.base import BaseConfig
from app.config.field_types import LowercaseHeaderName


class ForwardingSettings(BaseConfig):
    connect_timeout_seconds: PositiveFloat = Field(default=5.0)
    timeout_seconds: PositiveFloat = Field(default=28.0)
    edge_header_prefix: LowercaseHeaderName = Field(default="x-edge-")
    recomputed_response_headers: frozenset[LowercaseHeaderName] = Field(
        default=frozenset({"content-length", "content-encoding", "transfer-encoding", "connection"})
    )

    @model_validator(mode="after")
    def connect_within_the_total(self) -> Self:
        if self.connect_timeout_seconds >= self.timeout_seconds:
            raise ValueError("connect_timeout_seconds must be shorter than timeout_seconds")
        return self
