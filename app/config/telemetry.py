from pydantic import Field

from app.config.base import FrozenModel


class TelemetrySettings(FrozenModel):
    service_name: str = Field(default="cluster-client")
    export_enabled: bool = Field(default=False)
    otlp_endpoint: str = Field(default="http://localhost:4318", pattern=r"[^/]$")
    traces_path: str = Field(default="/v1/traces", pattern=r"^/")
