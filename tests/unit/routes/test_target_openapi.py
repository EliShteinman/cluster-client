from app.config.settings import NoEnvFileSettings, Settings
from app.routes.target_openapi import documented_target_headers, failure_responses, target_request_headers
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
