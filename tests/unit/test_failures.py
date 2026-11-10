import json
from types import SimpleNamespace

import pytest
from fastapi import Request, Response
from starlette.exceptions import HTTPException

from app.config.failures import FailureCode, FailureSettings
from app.config.settings import NoEnvFileSettings, Settings
from app.errors import ConnectionFailedError, NoResponseError, RequestFailedError, ResponseRejectedError
from app.failures.codes import failure_code
from app.failures.handlers import internal_error_response, refused_request_response
from app.failures.log import failure_record, redacted_content
from app.failures.response import failure_response
from app.field_paths import FieldPath
from app.models import ClusterResponse, RequestFailure
from tests.support.requests import CLUSTER_REQUEST, CLUSTER_URL

SETTINGS: Settings = NoEnvFileSettings()
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
        failures=FailureSettings(rejected=FailureCode(status_code=422, error_code="bad"))
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


def test_an_unexpected_error_is_marked_as_our_own_answer() -> None:
    response: Response = internal_error_response(REQUEST, RecursionError("too deep"))

    assert (response.status_code, response.headers["x-edge-error"]) == (500, "internal_error")


def test_an_unexpected_error_does_not_return_its_message() -> None:
    response: Response = internal_error_response(REQUEST, ValueError("secret value"))

    assert bytes(response.body) == b'{"error":"internal_error","reason":"ValueError"}'
