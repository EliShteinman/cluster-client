from pydantic import Field

from app.config.base import BaseConfig
from app.config.field_types import ErrorStatusCode, HeaderName


class FailureCode(BaseConfig):
    status_code: ErrorStatusCode
    error_code: str


class FailureSettings(BaseConfig):
    invalid_request: FailureCode = Field(default=FailureCode(status_code=400, error_code="invalid_request"))
    rejected: FailureCode = Field(default=FailureCode(status_code=502, error_code="response_rejected"))
    connection_failed: FailureCode = Field(
        default=FailureCode(status_code=502, error_code="connection_failed")
    )
    no_response: FailureCode = Field(default=FailureCode(status_code=504, error_code="timeout"))
    internal_error: FailureCode = Field(default=FailureCode(status_code=500, error_code="internal_error"))
    error_header: HeaderName = Field(default="x-edge-error")
    cluster_status_header: HeaderName = Field(default="x-edge-cluster-status")
    content_type: str = Field(default="application/json")
