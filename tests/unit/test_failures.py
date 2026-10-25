import json
import logging

import pytest

from app.config import FailureSettings, Settings
from app.errors import ConnectionFailedError, NoResponseError, RequestFailedError, ResponseRejectedError
from app.failures import failure_code, failure_record, failure_response, record_failure
from app.models import ClusterResponse, RequestFailure
from tests.support.requests import CLUSTER_REQUEST, CLUSTER_URL

SETTINGS: Settings = Settings(_env_file=None)
CONNECTION_FAILED: ConnectionFailedError = ConnectionFailedError(url=CLUSTER_URL, reason="refused")
NO_RESPONSE: NoResponseError = NoResponseError(url=CLUSTER_URL, reason="read timed out")
REJECTION: ResponseRejectedError = ResponseRejectedError(
    field="$.uid", reason="'one' is not of type 'integer'"
)
CLUSTER_RESPONSE: ClusterResponse = ClusterResponse(status_code=200, content=b'{"uid": "one"}')


@pytest.mark.parametrize(
    ("failure", "error_code"),
    [(CONNECTION_FAILED, "connection_failed"), (NO_RESPONSE, "timeout"), (REJECTION, "response_rejected")],
)
def test_each_failure_gets_its_configured_code(failure: RequestFailedError, error_code: str) -> None:
    assert failure_code(failure=failure, settings=FailureSettings()).error_code == error_code


def test_record_without_cluster_response_has_no_cluster_fields() -> None:
    record: RequestFailure = failure_record(
        request=CLUSTER_REQUEST, failure=CONNECTION_FAILED, cluster_response=None, settings=SETTINGS.failures
    )

    assert (record.cluster_status_code, record.cluster_response) == (None, None)


def test_record_keeps_the_full_cluster_response() -> None:
    record: RequestFailure = failure_record(
        request=CLUSTER_REQUEST,
        failure=REJECTION,
        cluster_response=CLUSTER_RESPONSE,
        settings=SETTINGS.failures,
    )

    assert (record.cluster_status_code, record.cluster_response) == (200, '{"uid": "one"}')


def test_record_names_the_request() -> None:
    record: RequestFailure = failure_record(
        request=CLUSTER_REQUEST,
        failure=REJECTION,
        cluster_response=CLUSTER_RESPONSE,
        settings=SETTINGS.failures,
    )

    assert (record.method, record.url, record.field) == ("GET", CLUSTER_URL, "$.uid")


def test_failure_is_written_to_the_failure_logger(caplog: pytest.LogCaptureFixture) -> None:
    caplog.set_level(level=logging.WARNING, logger=SETTINGS.log.failure_file.logger_name)

    record_failure(
        request=CLUSTER_REQUEST, failure=REJECTION, cluster_response=CLUSTER_RESPONSE, settings=SETTINGS
    )

    assert caplog.records[-1].cluster_response == '{"uid": "one"}'


def test_response_uses_the_configured_status_code() -> None:
    settings: Settings = Settings(
        _env_file=None, failures=FailureSettings(rejected={"status_code": 422, "error_code": "bad"})
    )

    assert failure_response(failure=REJECTION, cluster_response=None, settings=settings).status_code == 422


def test_response_body_describes_the_failure() -> None:
    response: ClusterResponse = failure_response(failure=REJECTION, cluster_response=None, settings=SETTINGS)

    assert json.loads(s=response.content) == {
        "error": "response_rejected",
        "reason": REJECTION.reason,
        "field": "$.uid",
    }


def test_response_body_omits_a_missing_field() -> None:
    response: ClusterResponse = failure_response(
        failure=CONNECTION_FAILED, cluster_response=None, settings=SETTINGS
    )

    assert "field" not in json.loads(s=response.content)


def test_response_has_the_configured_content_type() -> None:
    response: ClusterResponse = failure_response(
        failure=CONNECTION_FAILED, cluster_response=None, settings=SETTINGS
    )

    assert response.headers["content-type"] == "application/json"


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


def test_no_cluster_status_without_a_cluster_response() -> None:
    response: ClusterResponse = failure_response(
        failure=CONNECTION_FAILED, cluster_response=None, settings=SETTINGS
    )

    assert "x-edge-cluster-status" not in response.headers
