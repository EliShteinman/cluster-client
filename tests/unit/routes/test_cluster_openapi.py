from app.config.settings import NoEnvFileSettings, Settings
from app.routes.cluster_openapi import cluster_request_headers, failure_responses

SETTINGS: Settings = NoEnvFileSettings()


def test_failure_codes_sharing_a_status_are_documented_together() -> None:
    assert failure_responses(settings=SETTINGS)[502]["description"] == "response_rejected, connection_failed"


def test_cluster_request_headers_are_required_like_their_fields() -> None:
    assert [header["required"] for header in cluster_request_headers(settings=SETTINGS)] == [
        True,
        True,
        True,
        False,
    ]
