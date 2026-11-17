from typing import cast

from app.config.settings import NoEnvFileSettings, Settings
from app.routes.target_openapi import (
    documented_target_headers,
    failure_responses,
    target_request_headers,
    trace_request_header,
)
from tests.support.access import ACCESS

SETTINGS: Settings = NoEnvFileSettings(access=ACCESS)


def test_failure_codes_sharing_a_status_are_documented_together() -> None:
    assert failure_responses(settings=SETTINGS)[502]["description"] == "response_rejected, connection_failed"


def test_the_own_headers_are_documented_as_required() -> None:
    assert [(header["name"], header["required"]) for header in target_request_headers(settings=SETTINGS)] == [
        ("x-edge-method", True),
        ("x-edge-url", True),
    ]


def test_documented_target_headers_carry_the_prefix() -> None:
    assert [header["name"] for header in documented_target_headers(settings=SETTINGS)] == [
        "x-target-authorization",
        "x-target-content-type",
    ]


def test_the_login_challenge_is_documented_on_unauthorized() -> None:
    unauthorized: dict[str, object] = failure_responses(settings=SETTINGS)[401]
    headers: dict[str, object] = cast(typ=dict[str, object], val=unauthorized["headers"])

    assert "www-authenticate" in headers


def test_the_trace_header_is_documented_as_optional() -> None:
    assert trace_request_header(settings=SETTINGS.telemetry)["required"] is False


def test_every_documented_failure_carries_the_trace_response_header() -> None:
    assert all(
        "traceresponse" in cast(typ=dict[str, object], val=failure["headers"])
        for failure in failure_responses(settings=SETTINGS).values()
    )


def test_every_documented_failure_carries_the_exposed_headers_header() -> None:
    assert all(
        "access-control-expose-headers" in cast(typ=dict[str, object], val=failure["headers"])
        for failure in failure_responses(settings=SETTINGS).values()
    )
