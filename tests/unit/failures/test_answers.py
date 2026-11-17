# pyright: reportUnknownMemberType=false
import json
import logging
import traceback
from collections.abc import Callable
from types import SimpleNamespace

import pytest
from fastapi import HTTPException, Request, Response
from jsonschema.protocols import Validator

from app.config.failures import FailureCode, FailureSettings
from app.config.settings import NoEnvFileSettings, Settings
from app.errors import (
    AccessDeniedError,
    ConnectionFailedError,
    InvalidTargetRequestError,
    NoResponseError,
    RequestFailedError,
    ResponseRejectedError,
)
from app.failures.answers import failed_request_answer, failure_code, failure_record, redacted_content
from app.failures.exception_handlers import (
    access_denied_response,
    internal_error_response,
    refused_request_response,
)
from app.models import Answer, FailureRecord
from app.rules.field_paths import FieldPath
from app.rules.schema import validate_body
from tests.support.access import ACCESS
from tests.support.requests import TARGET_REQUEST, TARGET_URL
from tests.support.rules import DRAFT_04, RULES, validator_of

SETTINGS: Settings = NoEnvFileSettings(access=ACCESS)
CONNECTION_FAILED: ConnectionFailedError = ConnectionFailedError(url=TARGET_URL, reason="refused")
NO_RESPONSE: NoResponseError = NoResponseError(url=TARGET_URL, reason="read timed out")
REJECTION: ResponseRejectedError = ResponseRejectedError(
    field="$.uid", reason="'one' is not of type 'integer'"
)
TARGET_RESPONSE: Answer = Answer(status_code=200, content=b'{"uid": "one"}')
REDACT_PASSWORD: tuple[FieldPath, ...] = (("password",),)
REQUEST: Request = Request(
    scope={
        "type": "http",
        "app": SimpleNamespace(state=SimpleNamespace(settings=SETTINGS, rules=RULES)),
    }
)


LONG_TEXT: str = "too long " * 400
HUGE_TEXT: str = "x" * (RULES.error_limits.part_length * RULES.error_limits.max_parts + 10)
HUGE_REJECTION: ResponseRejectedError = ResponseRejectedError(
    rule="anyOf", field="$" + ".a" * 300, reason=HUGE_TEXT
)
LONG_REJECTION: ResponseRejectedError = ResponseRejectedError(
    rule="anyOf", field="$" + ".a" * 300, reason=LONG_TEXT
)
NOT_JSON: ResponseRejectedError = ResponseRejectedError(rule="not_json", field="$", reason=LONG_TEXT)
LONG_CONNECTION_FAILURE: ConnectionFailedError = ConnectionFailedError(url=TARGET_URL, reason=LONG_TEXT)
LONG_NO_RESPONSE: NoResponseError = NoResponseError(url=TARGET_URL, reason=LONG_TEXT)
HEADER_ERRORS: list[dict[str, object]] = [
    {"type": "missing", "loc": ["x-edge-url"], "msg": LONG_TEXT} for _ in range(3)
]
FIREWALL: Validator = RULES.schema_validator
REDACT_ADMIN_PASSWORD: tuple[FieldPath, ...] = (("authentication_admin_pass",),)
BDB_WITH_PASSWORD: bytes = b'{"uid": 1, "name": "db", "authentication_admin_pass": "TOPSECRET"}'
TOO_MANY_PROPERTIES: Validator = validator_of(schema={"$schema": DRAFT_04, "maxProperties": 1})


def password_rejection() -> ResponseRejectedError:
    with pytest.raises(ResponseRejectedError) as raised:
        validate_body(
            body=json.loads(s=BDB_WITH_PASSWORD),
            schema=TOO_MANY_PROPERTIES,
            redacted_fields=REDACT_ADMIN_PASSWORD,
            redacted_reason=SETTINGS.failures.redacted_reason,
        )
    return raised.value


def raised_error(*, message: str = "disk is full") -> ValueError:
    try:
        raise ValueError(message)
    except ValueError as error:
        return error


def content_of(*, answer: Answer | Response) -> bytes:
    return answer.content if isinstance(answer, Answer) else bytes(answer.body)


def reason_of(*, response: Response) -> str:
    return "".join(json.loads(s=bytes(response.body))["reason"])


def record_of(*, failure: RequestFailedError) -> FailureRecord:
    return failure_record(
        request=TARGET_REQUEST,
        failure=failure,
        error_code="response_rejected",
        target_response=None,
        redacted_fields=REDACT_PASSWORD,
    )


def record(*, target_response: Answer | None) -> FailureRecord:
    return failure_record(
        request=TARGET_REQUEST,
        failure=REJECTION,
        error_code="response_rejected",
        target_response=target_response,
        redacted_fields=REDACT_PASSWORD,
    )


@pytest.mark.parametrize(
    ("failure", "error_code"),
    [
        (CONNECTION_FAILED, "connection_failed"),
        (NO_RESPONSE, "timeout"),
        (REJECTION, "response_rejected"),
        (InvalidTargetRequestError(url=TARGET_URL, reason="bad url"), "invalid_request"),
    ],
)
def test_each_failure_gets_its_configured_code(failure: RequestFailedError, error_code: str) -> None:
    assert failure_code(failure=failure, settings=FailureSettings()).error_code == error_code


def test_record_leaves_out_the_redacted_fields() -> None:
    failure: FailureRecord = record(
        target_response=Answer(status_code=200, content=b'{"uid": "one", "password": "s3cret"}')
    )

    assert json.loads(s=failure.target_response or "") == {"uid": "one"}


def test_content_that_is_not_json_is_kept_as_text() -> None:
    assert redacted_content(content=b"<html>", redacted_fields=REDACT_PASSWORD) == "<html>"


def test_response_uses_the_configured_status_code() -> None:
    settings: Settings = NoEnvFileSettings(
        access=ACCESS, failures=FailureSettings(rejected=FailureCode(status_code=422, error_code="bad"))
    )

    assert (
        failed_request_answer(
            request=TARGET_REQUEST, failure=REJECTION, target_response=None, rules=RULES, settings=settings
        ).status_code
        == 422
    )


def test_response_is_marked_with_the_error_code() -> None:
    response: Answer = failed_request_answer(
        request=TARGET_REQUEST, failure=NO_RESPONSE, target_response=None, rules=RULES, settings=SETTINGS
    )

    assert response.headers["x-edge-error"] == "timeout"


def test_rejection_carries_the_target_status() -> None:
    response: Answer = failed_request_answer(
        request=TARGET_REQUEST,
        failure=REJECTION,
        target_response=Answer(status_code=201),
        rules=RULES,
        settings=SETTINGS,
    )

    assert response.headers["x-edge-target-status"] == "201"


def test_a_failure_without_a_target_answer_carries_no_target_status() -> None:
    response: Answer = failed_request_answer(
        request=TARGET_REQUEST, failure=NO_RESPONSE, target_response=None, rules=RULES, settings=SETTINGS
    )

    assert "x-edge-target-status" not in response.headers


def test_a_refused_request_is_marked_as_our_own_answer() -> None:
    response: Response = refused_request_response(REQUEST, HTTPException(status_code=404))

    assert response.headers["x-edge-error"] == "invalid_request"


def test_a_refused_request_keeps_its_headers() -> None:
    error: HTTPException = HTTPException(status_code=405, headers={"allow": "POST"})

    assert refused_request_response(REQUEST, error).headers["allow"] == "POST"


def test_a_refused_header_reason_is_json() -> None:
    response: Response = refused_request_response(
        REQUEST, HTTPException(status_code=400, detail=[{"type": "missing", "loc": ("x-edge-url",)}])
    )

    assert json.loads(s=reason_of(response=response)) == [{"type": "missing", "loc": ["x-edge-url"]}]


def test_denied_access_gets_the_configured_status() -> None:
    assert access_denied_response(REQUEST, AccessDeniedError(header="authorization")).status_code == 401


def test_denied_access_is_marked_as_our_own_answer() -> None:
    response: Response = access_denied_response(REQUEST, AccessDeniedError(header="authorization"))

    assert response.headers["x-edge-error"] == "unauthorized"


def test_denied_access_asks_for_basic_credentials() -> None:
    response: Response = access_denied_response(REQUEST, AccessDeniedError(header="authorization"))

    assert response.headers["www-authenticate"] == 'Basic realm="cluster-client"'


def test_an_unexpected_error_gets_the_configured_status() -> None:
    assert internal_error_response(REQUEST, RecursionError("too deep")).status_code == 500


def test_an_unexpected_error_is_marked_as_our_own_answer() -> None:
    response: Response = internal_error_response(REQUEST, RecursionError("too deep"))

    assert response.headers["x-edge-error"] == "internal_error"


def test_an_unexpected_error_returns_its_message() -> None:
    assert "disk is full" in reason_of(response=internal_error_response(REQUEST, raised_error()))


def test_an_unexpected_error_returns_its_traceback() -> None:
    assert "raised_error" in reason_of(response=internal_error_response(REQUEST, raised_error()))


def test_rejected_password_is_left_out_of_the_answer() -> None:
    response: Answer = failed_request_answer(
        request=TARGET_REQUEST,
        failure=password_rejection(),
        target_response=None,
        rules=RULES,
        settings=SETTINGS,
    )

    assert b"TOPSECRET" not in response.content


def test_rejected_password_is_left_out_of_the_failure_record() -> None:
    failure: FailureRecord = failure_record(
        request=TARGET_REQUEST,
        failure=password_rejection(),
        error_code="response_rejected",
        target_response=Answer(status_code=200, content=BDB_WITH_PASSWORD),
        redacted_fields=REDACT_ADMIN_PASSWORD,
    )

    assert "TOPSECRET" not in failure.model_dump_json()


@pytest.mark.parametrize(
    "answer",
    [
        lambda: failed_request_answer(
            request=TARGET_REQUEST,
            failure=LONG_REJECTION,
            target_response=None,
            rules=RULES,
            settings=SETTINGS,
        ),
        lambda: failed_request_answer(
            request=TARGET_REQUEST, failure=NOT_JSON, target_response=None, rules=RULES, settings=SETTINGS
        ),
        lambda: failed_request_answer(
            request=TARGET_REQUEST,
            failure=LONG_CONNECTION_FAILURE,
            target_response=None,
            rules=RULES,
            settings=SETTINGS,
        ),
        lambda: failed_request_answer(
            request=TARGET_REQUEST,
            failure=LONG_NO_RESPONSE,
            target_response=None,
            rules=RULES,
            settings=SETTINGS,
        ),
        lambda: refused_request_response(REQUEST, HTTPException(status_code=400, detail=HEADER_ERRORS)),
        lambda: internal_error_response(REQUEST, raised_error(message=LONG_TEXT)),
        lambda: access_denied_response(REQUEST, AccessDeniedError(header="authorization")),
    ],
    ids=[
        "rejection",
        "not json",
        "connection failed",
        "timeout",
        "invalid request",
        "internal error",
        "unauthorized",
    ],
)
def test_every_own_answer_passes_the_firewall(answer: Callable[[], Answer | Response]) -> None:
    assert FIREWALL.is_valid(instance=json.loads(s=content_of(answer=answer())))


def test_failure_record_keeps_the_whole_reason() -> None:
    assert record_of(failure=HUGE_REJECTION).reason == HUGE_TEXT


def test_failure_record_keeps_the_whole_field() -> None:
    assert record_of(failure=HUGE_REJECTION).field == HUGE_REJECTION.field


def test_an_unexpected_error_logs_its_whole_traceback(caplog: pytest.LogCaptureFixture) -> None:
    error: ValueError = raised_error(message=HUGE_TEXT)
    with caplog.at_level(level=logging.ERROR, logger=SETTINGS.log.failure_file.logger_name):
        internal_error_response(REQUEST, error)

    assert caplog.records[-1].__dict__["reason"] == "".join(traceback.format_exception(error))


def test_a_refused_request_logs_its_whole_reason(caplog: pytest.LogCaptureFixture) -> None:
    with caplog.at_level(level=logging.WARNING, logger=SETTINGS.log.failure_file.logger_name):
        refused_request_response(REQUEST, HTTPException(status_code=400, detail=HUGE_TEXT))

    assert caplog.records[-1].__dict__["reason"] == HUGE_TEXT
