import json
import logging

import pytest

from app.config import FailureSettings, Settings
from app.errors import ClusterUnreachableError, RequestFailedError, ResponseRejectedError
from app.failures import failure_code, failure_record, failure_response, record_failure
from app.models import ClusterResponse, RequestFailure
from tests.support.requests import CLUSTER_REQUEST, CLUSTER_URL

SETTINGS: Settings = Settings(_env_file=None)
UNREACHABLE: ClusterUnreachableError = ClusterUnreachableError(url=CLUSTER_URL, reason="refused")
REJECTION: ResponseRejectedError = ResponseRejectedError(
    field="$.uid", reason="'one' is not of type 'integer'"
)
CLUSTER_RESPONSE: ClusterResponse = ClusterResponse(status_code=200, content=b'{"uid": "one"}')


@pytest.mark.parametrize(
    ("failure", "error_code"), [(UNREACHABLE, "cluster_unreachable"), (REJECTION, "response_rejected")]
)
def test_each_failure_gets_its_configured_code(failure: RequestFailedError, error_code: str) -> None:
    assert failure_code(failure=failure, settings=FailureSettings()).error_code == error_code


def test_record_without_cluster_response_has_no_cluster_fields() -> None:
    record: RequestFailure = failure_record(
        request=CLUSTER_REQUEST, failure=UNREACHABLE, cluster_response=None, settings=SETTINGS.failures
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

    assert failure_response(failure=REJECTION, settings=settings).status_code == 422


def test_response_body_describes_the_failure() -> None:
    response: ClusterResponse = failure_response(failure=REJECTION, settings=SETTINGS)

    assert json.loads(s=response.content) == {
        "error": "response_rejected",
        "reason": REJECTION.reason,
        "field": "$.uid",
    }


def test_response_body_omits_a_missing_field() -> None:
    assert "field" not in json.loads(s=failure_response(failure=UNREACHABLE, settings=SETTINGS).content)


def test_response_has_the_configured_content_type() -> None:
    assert failure_response(failure=UNREACHABLE, settings=SETTINGS).headers == {
        "content-type": "application/json"
    }
