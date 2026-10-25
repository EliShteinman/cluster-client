import asyncio
from collections.abc import Iterator
from pathlib import Path

import pytest
import requests
from fastapi import FastAPI

from app.config import ForwardingSettings, ServerSettings, Settings
from app.main import create_app
from tests.support.app_settings import make_app_settings
from tests.support.live_server import free_port, live_server
from tests.support.schemas import DATABASE_SCHEMA, write_schema

FORWARDING_TIMEOUT_SECONDS: float = 0.3
SLOW_ANSWER_SECONDS: float = 1.0


def fake_cluster_app() -> FastAPI:
    cluster_api: FastAPI = FastAPI()

    @cluster_api.get("/v1/bdbs/{uid}")
    async def database(*, uid: int) -> dict[str, int | str]:
        return {"uid": uid, "name": "db"} if uid == 1 else {"uid": "broken"}

    @cluster_api.get("/slow")
    async def slow() -> dict[str, int]:
        await asyncio.sleep(SLOW_ANSWER_SECONDS)
        return {"uid": 1}

    return cluster_api


@pytest.fixture(scope="module")
def cluster_url() -> Iterator[str]:
    with live_server(app=fake_cluster_app(), port=free_port()) as url:
        yield url


@pytest.fixture(scope="module")
def client_url(tmp_path_factory: pytest.TempPathFactory) -> Iterator[str]:
    folder: Path = tmp_path_factory.mktemp("cluster-client")
    settings: Settings = make_app_settings(
        log_path=folder / "app.log",
        failure_log_path=folder / "failures.log",
        schema_path=write_schema(path=folder / "schema.json", schema=DATABASE_SCHEMA),
        server=ServerSettings(port=free_port()),
        forwarding=ForwardingSettings(timeout_seconds=FORWARDING_TIMEOUT_SECONDS),
    )
    with live_server(app=create_app(settings=settings), port=settings.server.port) as url:
        yield url


def send(*, client_url: str, cluster_url: str, path: str) -> requests.Response:
    return requests.post(
        url=f"{client_url}/",
        headers={
            "x-cluster-method": "GET",
            "x-cluster-url": f"{cluster_url}{path}",
            "x-cluster-authorization": "Basic abc",
        },
        timeout=10,
    )


@pytest.mark.parametrize("path", ["/health/live", "/health/ready"])
def test_health_endpoint_answers_up(client_url: str, path: str) -> None:
    assert requests.get(url=f"{client_url}{path}", timeout=10).json() == {"status": "up"}


def test_valid_cluster_response_is_returned(client_url: str, cluster_url: str) -> None:
    assert send(client_url=client_url, cluster_url=cluster_url, path="/v1/bdbs/1").json() == {
        "uid": 1,
        "name": "db",
    }


def test_invalid_cluster_response_is_rejected(client_url: str, cluster_url: str) -> None:
    assert send(client_url=client_url, cluster_url=cluster_url, path="/v1/bdbs/2").status_code == 502


def test_closed_port_is_a_connection_failure(client_url: str) -> None:
    response: requests.Response = send(
        client_url=client_url, cluster_url=f"http://127.0.0.1:{free_port()}", path="/v1/bdbs/1"
    )

    assert response.headers["x-edge-error"] == "connection_failed"


def test_slow_cluster_is_a_timeout(client_url: str, cluster_url: str) -> None:
    response: requests.Response = send(client_url=client_url, cluster_url=cluster_url, path="/slow")

    assert response.headers["x-edge-error"] == "timeout"
