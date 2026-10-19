import logging
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from tests.support.logging_settings import read_json_lines


@pytest.mark.parametrize("path", ["/health/live", "/health/ready"])
def test_health_endpoint_reports_up(client: TestClient, path: str) -> None:
    assert client.get(path).json() == {"status": "up"}


def test_response_carries_the_trace_header(client: TestClient) -> None:
    assert "traceparent" in client.get("/health/live").headers


def test_logs_go_to_the_configured_file(client: TestClient, log_path: Path) -> None:
    logging.getLogger("app").info("written by the app")

    assert read_json_lines(log_path=log_path)[-1]["message"] == "written by the app"
