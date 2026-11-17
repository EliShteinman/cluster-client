from typing import cast

import pytest
from fastapi import HTTPException
from pydantic_core import ErrorDetails

from app.config.failures import FailureCode, FailureSettings
from app.config.headers import HeaderSettings
from app.config.settings import NoEnvFileSettings, Settings
from app.models import TargetRequest
from app.routes.read_request import read_target_request
from tests.support.access import ACCESS
from tests.support.requests import TARGET_HEADERS, TARGET_URL

SETTINGS: Settings = NoEnvFileSettings(
    access=ACCESS,
    failures=FailureSettings(invalid_request=FailureCode(status_code=422, error_code="bad_request")),
)
UNNORMALIZED_URL: str = "https://Cluster:443/v1/bdbs?name=a b&fields=uid,name"


def read(*, headers: dict[str, str], settings: Settings = SETTINGS) -> TargetRequest:
    return read_target_request(headers=headers, body=b"", settings=settings)


def refusal(*, headers: dict[str, str]) -> HTTPException:
    with pytest.raises(HTTPException) as raised:
        read(headers=headers)
    return raised.value


def without(*, name: str) -> dict[str, str]:
    return {header: value for header, value in TARGET_HEADERS.items() if header != name}


def test_the_method_header_becomes_the_method() -> None:
    assert read(headers=TARGET_HEADERS).method == "GET"


def test_the_url_header_becomes_the_url() -> None:
    assert read(headers=TARGET_HEADERS).url == TARGET_URL


def test_the_body_is_kept() -> None:
    assert read_target_request(headers=TARGET_HEADERS, body=b"{}", settings=SETTINGS).body == b"{}"


@pytest.mark.parametrize("missing", ["x-edge-method", "x-edge-url"])
def test_missing_own_header_is_refused_with_the_configured_status(missing: str) -> None:
    assert refusal(headers=without(name=missing)).status_code == 422


def test_refusal_names_the_missing_header() -> None:
    details: list[ErrorDetails] = cast(
        typ=list[ErrorDetails], val=refusal(headers=without(name="x-edge-url")).detail
    )

    assert [detail["loc"] for detail in details] == [("x-edge-url",)]


def test_own_header_names_come_from_the_given_settings() -> None:
    settings: Settings = NoEnvFileSettings(access=ACCESS, headers=HeaderSettings(method="X-Verb"))
    headers: dict[str, str] = {**without(name="x-edge-method"), "x-verb": "POST"}

    assert read(headers=headers, settings=settings).method == "POST"


def test_target_headers_are_sent_without_the_prefix() -> None:
    headers: dict[str, str] = {**TARGET_HEADERS, "x-target-cluster-state-id": "155"}

    assert read(headers=headers).headers == {"authorization": "Basic abc", "cluster-state-id": "155"}


def test_no_other_header_reaches_the_target() -> None:
    headers: dict[str, str] = {
        **TARGET_HEADERS,
        "authorization": "Basic access",
        "x-forwarded-for": "10.0.0.1",
    }

    assert read(headers=headers).headers == {"authorization": "Basic abc"}


def test_a_request_without_target_authorization_is_accepted() -> None:
    assert read(headers=without(name="x-target-authorization")).headers == {}


@pytest.mark.parametrize("header", ["x-target-host", "x-target-content-length", "x-target-transfer-encoding"])
def test_a_hop_by_hop_target_header_is_refused(header: str) -> None:
    assert refusal(headers={**TARGET_HEADERS, header: "x"}).status_code == 422


def test_the_refusal_names_the_refused_header() -> None:
    assert "x-target-host" in str(refusal(headers={**TARGET_HEADERS, "x-target-host": "x"}).detail)


def test_a_target_header_without_a_name_is_refused() -> None:
    assert refusal(headers={**TARGET_HEADERS, "x-target-": "x"}).status_code == 422


def test_the_url_is_kept_as_received() -> None:
    assert read(headers={**TARGET_HEADERS, "x-edge-url": UNNORMALIZED_URL}).url == UNNORMALIZED_URL


def test_a_long_url_is_accepted() -> None:
    long_url: str = TARGET_URL + "?fields=" + "a" * 5000

    assert read(headers={**TARGET_HEADERS, "x-edge-url": long_url}).url == long_url


def test_a_url_that_is_not_http_is_refused() -> None:
    assert refusal(headers={**TARGET_HEADERS, "x-edge-url": "ftp://cluster/file"}).status_code == 422


@pytest.mark.parametrize("method", ["PROPFIND", "get", "M-SEARCH"])
def test_any_method_token_is_sent_as_received(method: str) -> None:
    assert read(headers={**TARGET_HEADERS, "x-edge-method": method}).method == method


def test_a_method_that_is_not_a_token_is_refused() -> None:
    assert refusal(headers={**TARGET_HEADERS, "x-edge-method": "GE T"}).status_code == 422
