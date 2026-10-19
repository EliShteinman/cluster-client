from collections.abc import Iterator
from unittest.mock import Mock, patch

import pytest
from fastapi import FastAPI

from app.config import ServerSettings
from app.server import serve

SETTINGS: ServerSettings = ServerSettings(host="10.0.0.1", port=9100, server_header=True)
APP: FastAPI = FastAPI()


@pytest.fixture
def uvicorn_run() -> Iterator[Mock]:
    with patch("app.server.uvicorn.run") as run:
        serve(app=APP, settings=SETTINGS)
        yield run


def test_serves_the_given_app(uvicorn_run: Mock) -> None:
    assert uvicorn_run.call_args.kwargs["app"] is APP


@pytest.mark.parametrize(
    ("option", "expected"),
    [("host", "10.0.0.1"), ("port", 9100), ("server_header", True), ("date_header", False)],
)
def test_passes_server_option(uvicorn_run: Mock, option: str, expected: object) -> None:
    assert uvicorn_run.call_args.kwargs[option] == expected


def test_leaves_logging_configuration_to_the_logger(uvicorn_run: Mock) -> None:
    assert uvicorn_run.call_args.kwargs["log_config"] is None
