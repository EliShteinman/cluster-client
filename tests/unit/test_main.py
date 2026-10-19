import pytest
from fastapi import FastAPI

from app.config import Settings
from app.main import create_app


def test_trace_middleware_is_added(app_settings: Settings) -> None:
    names: list[str] = [entry.cls.__name__ for entry in create_app(settings=app_settings).user_middleware]

    assert names == ["TraceMiddleware"]


def test_title_and_version_come_from_settings(app_settings: Settings) -> None:
    app: FastAPI = create_app(settings=app_settings)

    assert (app.title, app.version) == ("client-under-test", "0.0.0-test")


@pytest.mark.parametrize("path", ["/", "/health/live", "/health/ready"])
def test_route_is_included(app_settings: Settings, path: str) -> None:
    assert path in create_app(settings=app_settings).openapi()["paths"]
