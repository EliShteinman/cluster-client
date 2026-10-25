import pytest
from fastapi import HTTPException

from app.config import FailureSettings, ForwardingSettings, Settings
from app.models import ClusterRequest, HttpMethod
from app.routes.read_request import read_cluster_request
from tests.support.requests import CLUSTER_HEADERS, CLUSTER_URL

SETTINGS: Settings = Settings(
    _env_file=None,
    failures=FailureSettings(invalid_request_status_code=422),
    forwarding=ForwardingSettings(passed_through_request_headers=frozenset({"x-task-id"})),
)


def test_configured_headers_become_the_cluster_request() -> None:
    request: ClusterRequest = read_cluster_request(headers=CLUSTER_HEADERS, body=b"{}", settings=SETTINGS)

    assert (request.method, str(request.url), request.body) == (HttpMethod.GET, CLUSTER_URL, b"{}")


def test_method_header_is_read_in_any_case() -> None:
    request: ClusterRequest = read_cluster_request(
        headers={**CLUSTER_HEADERS, "x-cluster-method": "delete"}, body=b"", settings=SETTINGS
    )

    assert request.method is HttpMethod.DELETE


@pytest.mark.parametrize("missing", ["x-cluster-method", "x-cluster-url", "x-cluster-authorization"])
def test_missing_header_is_refused_with_the_configured_status(missing: str) -> None:
    headers: dict[str, str] = {name: value for name, value in CLUSTER_HEADERS.items() if name != missing}

    with pytest.raises(HTTPException) as raised:
        read_cluster_request(headers=headers, body=b"", settings=SETTINGS)

    assert raised.value.status_code == 422


def test_configured_headers_are_passed_through() -> None:
    request: ClusterRequest = read_cluster_request(
        headers={**CLUSTER_HEADERS, "x-task-id": "t1"}, body=b"", settings=SETTINGS
    )

    assert request.passed_through_headers == {"x-task-id": "t1"}


def test_other_headers_are_not_passed_through() -> None:
    request: ClusterRequest = read_cluster_request(
        headers={**CLUSTER_HEADERS, "x-other": "1"}, body=b"", settings=SETTINGS
    )

    assert request.passed_through_headers == {}
