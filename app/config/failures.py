import sys
from typing import Self

from pydantic import Field, model_validator

from app.config.base import BaseConfig
from app.config.field_types import ErrorStatusCode, HeaderName


class FailureCode(BaseConfig):
    status_code: ErrorStatusCode
    error_code: str


class FailureSettings(BaseConfig):
    invalid_request: FailureCode = Field(default=FailureCode(status_code=400, error_code="invalid_request"))
    unauthorized: FailureCode = Field(default=FailureCode(status_code=401, error_code="unauthorized"))
    rejected: FailureCode = Field(default=FailureCode(status_code=502, error_code="response_rejected"))
    connection_failed: FailureCode = Field(
        default=FailureCode(status_code=502, error_code="connection_failed")
    )
    no_response: FailureCode = Field(default=FailureCode(status_code=504, error_code="timeout"))
    internal_error: FailureCode = Field(default=FailureCode(status_code=500, error_code="internal_error"))
    error_header: HeaderName = Field(default="x-edge-error")
    cluster_status_header: HeaderName = Field(default="x-edge-cluster-status")
    content_type: str = Field(default="application/json")
    part_length: int = Field(default=256, gt=0)
    max_parts: int = Field(default=500, gt=1)
    shortened_field_prefix: str = Field(default="...")
    unsent_characters_message: str = Field(default="{count} more characters were not sent")
    not_json_rule: str = Field(default="not_json")
    not_json_reason: str = Field(default="the response body is not JSON: {error}")
    redacted_reason: str = Field(default="the failing value is a redacted field")

    @model_validator(mode="after")
    def fit_the_part_length(self) -> Self:
        try:
            unsent_message: str = self.unsent_characters_message.format(count=sys.maxsize)
            self.not_json_reason.format(error="")
        except (KeyError, IndexError, ValueError) as error:
            raise ValueError(f"a failure message has an unknown placeholder: {error}") from error
        if len(unsent_message) > self.part_length:
            raise ValueError("unsent_characters_message must fit in part_length")
        if len(self.shortened_field_prefix) >= self.part_length:
            raise ValueError("shortened_field_prefix must be shorter than part_length")
        return self
