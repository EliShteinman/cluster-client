# pyright: reportUnknownMemberType=false
import json
import logging
import traceback
from collections.abc import Callable
from pathlib import Path
from types import SimpleNamespace

import pytest
from fastapi import HTTPException, Request, Response
from jsonschema import Draft4Validator, Draft202012Validator

from app.config.failures import FailureCode, FailureSettings
from app.config.settings import NoEnvFileSettings, Settings
from app.errors import (
    AccessDeniedError,
    ConnectionFailedError,
    NoResponseError,
    RequestFailedError,
    ResponseRejectedError,
)
from app.failures.codes import failure_code
from app.failures.handlers import access_denied_response, internal_error_response, refused_request_response
from app.failures.log import failure_record, redacted_content
from app.failures.response import failure_response
from app.field_paths import FieldPath
from app.models import ClusterResponse, RequestFailure
from app.schema import validate_body
from tests.support.access import ACCESS
from tests.support.requests import CLUSTER_REQUEST, CLUSTER_URL

SETTINGS: Settings = NoEnvFileSettings(access=ACCESS)
CONNECTION_FAILED: ConnectionFailedError = ConnectionFailedError(url=CLUSTER_URL, reason="refused")
NO_RESPONSE: NoResponseError = NoResponseError(url=CLUSTER_URL, reason="read timed out")
REJECTION: ResponseRejectedError = ResponseRejectedError(
    field="$.uid", reason="'one' is not of type 'integer'"
)
CLUSTER_RESPONSE: ClusterResponse = ClusterResponse(status_code=200, content=b'{"uid": "one"}')
REDACT_PASSWORD: tuple[FieldPath, ...] = (("password",),)
REQUEST: Request = Request(
    scope={"type": "http", "app": SimpleNamespace(state=SimpleNamespace(settings=SETTINGS))}
)


LONG_TEXT: str = "too long " * 400
HUGE_TEXT: str = "x" * (512 * 500 + 10)
HUGE_REJECTION: ResponseRejectedError = ResponseRejectedError(
    rule="anyOf", field="$" + ".a" * 300, reason=HUGE_TEXT
)
LONG_REJECTION: ResponseRejectedError = ResponseRejectedError(
    rule="anyOf", field="$" + ".a" * 300, reason=LONG_TEXT
)
NOT_JSON: ResponseRejectedError = ResponseRejectedError(rule="not_json", field="$", reason=LONG_TEXT)
LONG_CONNECTION_FAILURE: ConnectionFailedError = ConnectionFailedError(url=CLUSTER_URL, reason=LONG_TEXT)
LONG_NO_RESPONSE: NoResponseError = NoResponseError(url=CLUSTER_URL, reason=LONG_TEXT)
HEADER_ERRORS: list[dict[str, object]] = [
    {"type": "missing", "loc": ["x-cluster-url"], "msg": LONG_TEXT} for _ in range(3)
]
FIREWALL: Draft4Validator = Draft4Validator(
    schema=json.loads(s=(Path(__file__).parents[1] / "support" / "firewall-response-schema.json").read_text())
)
REDACT_ADMIN_PASSWORD: tuple[FieldPath, ...] = (("authentication_admin_pass",),)
BDB_WITH_PASSWORD: bytes = b'{"uid": 1, "name": "db", "authentication_admin_pass": "TOPSECRET"}'
TOO_MANY_PROPERTIES: Draft202012Validator = Draft202012Validator(schema={"maxProperties": 1})


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


def content_of(*, answer: ClusterResponse | Response) -> bytes:
    return answer.content if isinstance(answer, ClusterResponse) else bytes(answer.body)


def reason_of(*, response: Response) -> str:
    return "".join(json.loads(s=bytes(response.body))["reason"])


def record_of(*, failure: RequestFailedError) -> RequestFailure:
    return failure_record(
        request=CLUSTER_REQUEST,
        failure=failure,
        cluster_response=None,
        redacted_fields=REDACT_PASSWORD,
        settings=SETTINGS.failures,
    )


def record(*, cluster_response: ClusterResponse | None) -> RequestFailure:
    return failure_record(
        request=CLUSTER_REQUEST,
        failure=REJECTION,
        cluster_response=cluster_response,
        redacted_fields=REDACT_PASSWORD,
        settings=SETTINGS.failures,
    )


@pytest.mark.parametrize(
    ("failure", "error_code"),
    [(CONNECTION_FAILED, "connection_failed"), (NO_RESPONSE, "timeout"), (REJECTION, "response_rejected")],
)
def test_each_failure_gets_its_configured_code(failure: RequestFailedError, error_code: str) -> None:
    assert failure_code(failure=failure, settings=FailureSettings()).error_code == error_code


def test_record_leaves_out_the_redacted_fields() -> None:
    failure: RequestFailure = record(
        cluster_response=ClusterResponse(status_code=200, content=b'{"uid": "one", "password": "s3cret"}')
    )

    assert json.loads(s=failure.cluster_response or "") == {"uid": "one"}


def test_content_that_is_not_json_is_kept_as_text() -> None:
    assert redacted_content(content=b"<html>", redacted_fields=REDACT_PASSWORD) == "<html>"


def test_response_uses_the_configured_status_code() -> None:
    settings: Settings = NoEnvFileSettings(
        access=ACCESS, failures=FailureSettings(rejected=FailureCode(status_code=422, error_code="bad"))
    )

    assert failure_response(failure=REJECTION, cluster_response=None, settings=settings).status_code == 422


def test_response_is_marked_with_the_error_code() -> None:
    response: ClusterResponse = failure_response(
        failure=NO_RESPONSE, cluster_response=None, settings=SETTINGS
    )

    assert response.headers["x-edge-error"] == "timeout"


def test_rejection_carries_the_cluster_status() -> None:
    response: ClusterResponse = failure_response(
        failure=REJECTION, cluster_response=ClusterResponse(status_code=201), settings=SETTINGS
    )

    assert response.headers["x-edge-cluster-status"] == "201"


def test_a_refused_request_is_marked_as_our_own_answer() -> None:
    response: Response = refused_request_response(REQUEST, HTTPException(status_code=404))

    assert response.headers["x-edge-error"] == "invalid_request"


def test_a_refused_request_keeps_its_headers() -> None:
    error: HTTPException = HTTPException(status_code=405, headers={"allow": "POST"})

    assert refused_request_response(REQUEST, error).headers["allow"] == "POST"


def test_denied_access_is_marked_as_our_own_answer() -> None:
    response: Response = access_denied_response(REQUEST, AccessDeniedError(header="authorization"))

    assert (response.status_code, response.headers["x-edge-error"]) == (401, "unauthorized")


def test_denied_access_asks_for_basic_credentials() -> None:
    response: Response = access_denied_response(REQUEST, AccessDeniedError(header="authorization"))

    assert response.headers["www-authenticate"] == 'Basic realm="cluster-client"'


def test_an_unexpected_error_is_marked_as_our_own_answer() -> None:
    response: Response = internal_error_response(REQUEST, RecursionError("too deep"))

    assert (response.status_code, response.headers["x-edge-error"]) == (500, "internal_error")


def test_an_unexpected_error_returns_its_message() -> None:
    assert "disk is full" in reason_of(response=internal_error_response(REQUEST, raised_error()))


def test_an_unexpected_error_returns_its_traceback() -> None:
    assert "raised_error" in reason_of(response=internal_error_response(REQUEST, raised_error()))


def test_rejected_password_is_left_out_of_the_answer() -> None:
    response: ClusterResponse = failure_response(
        failure=password_rejection(), cluster_response=None, settings=SETTINGS
    )

    assert b"TOPSECRET" not in response.content


def test_rejected_password_is_left_out_of_the_failure_record() -> None:
    failure: RequestFailure = failure_record(
        request=CLUSTER_REQUEST,
        failure=password_rejection(),
        cluster_response=ClusterResponse(status_code=200, content=BDB_WITH_PASSWORD),
        redacted_fields=REDACT_ADMIN_PASSWORD,
        settings=SETTINGS.failures,
    )

    assert "TOPSECRET" not in failure.model_dump_json()


@pytest.mark.parametrize(
    "answer",
    [
        lambda: failure_response(failure=LONG_REJECTION, cluster_response=None, settings=SETTINGS),
        lambda: failure_response(failure=NOT_JSON, cluster_response=None, settings=SETTINGS),
        lambda: failure_response(failure=LONG_CONNECTION_FAILURE, cluster_response=None, settings=SETTINGS),
        lambda: failure_response(failure=LONG_NO_RESPONSE, cluster_response=None, settings=SETTINGS),
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
def test_every_own_answer_passes_the_firewall(answer: Callable[[], ClusterResponse | Response]) -> None:
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
