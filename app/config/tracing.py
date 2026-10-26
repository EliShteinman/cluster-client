from pydantic import Field

from app.config.base import FrozenModel, HeaderName


class TracingSettings(FrozenModel):
    traceparent_header: HeaderName = Field(default="traceparent")
