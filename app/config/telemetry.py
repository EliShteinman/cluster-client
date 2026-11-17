from pydantic import Field

from app.config.base import BaseConfig
from app.config.constants import DISTRIBUTION_NAME
from app.config.field_types import LowercaseHeaderName


class TelemetrySettings(BaseConfig):
    service_name: str = Field(default=DISTRIBUTION_NAME)
    export_enabled: bool = Field(default=False)
    otlp_endpoint: str = Field(default="http://localhost:4318", pattern=r"[^/]$")
    traces_path: str = Field(default="/v1/traces", pattern=r"^/")
    trace_header: LowercaseHeaderName = Field(default="traceparent")
    trace_response_header: LowercaseHeaderName = Field(default="traceresponse")
