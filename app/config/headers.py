from typing import Self

from pydantic import Field, model_validator

from app.config.base import BaseConfig
from app.config.field_types import LowercaseHeaderName


class HeaderSettings(BaseConfig):
    method: LowercaseHeaderName = Field(default="x-edge-method")
    url: LowercaseHeaderName = Field(default="x-edge-url")
    target_prefix: LowercaseHeaderName = Field(default="x-target-")
    refused_target_headers: frozenset[LowercaseHeaderName] = Field(
        default=frozenset(
            {
                "connection",
                "content-length",
                "host",
                "keep-alive",
                "proxy-authenticate",
                "proxy-authorization",
                "proxy-connection",
                "te",
                "trailer",
                "transfer-encoding",
                "upgrade",
            }
        )
    )
    refused_reason: str = Field(
        default="{headers}: hop-by-hop and framing headers are never sent to the target"
    )
    documented_target_headers: tuple[LowercaseHeaderName, ...] = Field(
        default=("authorization", "content-type")
    )

    @model_validator(mode="after")
    def known_placeholders(self) -> Self:
        try:
            self.refused_reason.format(headers="")
        except (KeyError, IndexError, ValueError) as error:
            raise ValueError(f"refused_reason has an unknown placeholder: {error}") from error
        return self
