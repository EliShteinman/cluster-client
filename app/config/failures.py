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
    target_status_header: HeaderName = Field(default="x-edge-target-status")
    content_type_header: HeaderName = Field(default="content-type")
    content_type: str = Field(default="application/json")
    shortened_field_prefix: str = Field(default="...")
    unsent_characters_message: str = Field(default="{count} more characters were not sent")
    not_json_rule: str = Field(default="not_json")
    not_json_reason: str = Field(default="the response body is not JSON: {error}")
    too_deep_rule: str = Field(default="too_deep")
    too_deep_reason: str = Field(default="the response body is nested too deeply to be checked")
    redacted_reason: str = Field(default="the failing value is a redacted field")

    @model_validator(mode="after")
    def known_placeholders(self) -> Self:
        try:
            self.unsent_characters_message.format(count=0)
            self.not_json_reason.format(error="")
        except (KeyError, IndexError, ValueError) as error:
            raise ValueError(f"a failure message has an unknown placeholder: {error}") from error
        return self
