from typing import cast

import pytest
from fastapi import HTTPException
from pydantic_core import ErrorDetails

from app.config.failures import FailureCode, FailureSettings
from app.config.forwarding import ForwardingSettings
from app.config.headers import HeaderSettings
from app.config.settings import NoEnvFileSettings, Settings
from app.models import ClusterRequest, HttpMethod
from app.routes.read_request import read_cluster_request
from tests.support.requests import CLUSTER_HEADERS, CLUSTER_URL

SETTINGS: Settings = NoEnvFileSettings(
    failures=FailureSettings(invalid_request=FailureCode(status_code=422, error_code="bad_request")),
    forwarding=ForwardingSettings(passed_through_request_headers=frozenset({"x-task-id"})),
)


def test_configured_headers_become_the_cluster_request() -> None:
    request: ClusterRequest = read_cluster_request(headers=CLUSTER_HEADERS, body=b"{}", settings=SETTINGS)

    assert (request.method, str(request.url), request.body) == (HttpMethod.GET, CLUSTER_URL, b"{}")


@pytest.mark.parametrize("missing", ["x-cluster-method", "x-cluster-url", "x-cluster-authorization"])
def test_missing_header_is_refused_with_the_configured_status(missing: str) -> None:
    headers: dict[str, str] = {name: value for name, value in CLUSTER_HEADERS.items() if name != missing}

    with pytest.raises(HTTPException) as raised:
        read_cluster_request(headers=headers, body=b"", settings=SETTINGS)

    assert raised.value.status_code == 422


def test_refusal_names_the_missing_header() -> None:
    headers: dict[str, str] = {
        name: value for name, value in CLUSTER_HEADERS.items() if name != "x-cluster-url"
    }

    with pytest.raises(HTTPException) as raised:
        read_cluster_request(headers=headers, body=b"", settings=SETTINGS)

    details: list[ErrorDetails] = cast(typ=list[ErrorDetails], val=raised.value.detail)
    assert [detail["loc"] for detail in details] == [("x-cluster-url",)]


def test_header_names_come_from_the_given_settings() -> None:
    settings: Settings = NoEnvFileSettings(headers=HeaderSettings(method="X-Verb"))
    headers: dict[str, str] = {**CLUSTER_HEADERS, "x-verb": "POST"}
    del headers["x-cluster-method"]

    assert read_cluster_request(headers=headers, body=b"", settings=settings).method == HttpMethod.POST


def test_every_header_setting_names_a_request_field() -> None:
    assert set(HeaderSettings.model_fields) <= set(ClusterRequest.model_fields)


def test_configured_headers_are_passed_through() -> None:
    request: ClusterRequest = read_cluster_request(
        headers={**CLUSTER_HEADERS, "x-task-id": "t1"}, body=b"", settings=SETTINGS
    )

    assert request.passed_through_headers == {"x-task-id": "t1"}


def test_passed_through_header_is_configured_in_any_case() -> None:
    settings: Settings = NoEnvFileSettings(
        forwarding=ForwardingSettings(passed_through_request_headers=frozenset({"X-Task-Id"})),
    )

    request: ClusterRequest = read_cluster_request(
        headers={**CLUSTER_HEADERS, "x-task-id": "t1"}, body=b"", settings=settings
    )

    assert request.passed_through_headers == {"x-task-id": "t1"}


def test_other_headers_are_not_passed_through() -> None:
    request: ClusterRequest = read_cluster_request(
        headers={**CLUSTER_HEADERS, "x-other": "1"}, body=b"", settings=SETTINGS
    )

    assert request.passed_through_headers == {}
