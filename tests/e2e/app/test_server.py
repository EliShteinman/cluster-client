from collections.abc import Iterator
from pathlib import Path

import pytest
import requests
from fastapi import FastAPI

from app.config import ServerSettings, Settings
from app.main import create_app
from tests.support.app_settings import make_app_settings
from tests.support.live_server import free_port, live_server
from tests.support.schemas import DATABASE_SCHEMA, write_schema


def fake_cluster_app() -> FastAPI:
    cluster_api: FastAPI = FastAPI()

    @cluster_api.get("/v1/bdbs/{uid}")
    async def database(*, uid: int) -> dict[str, int | str]:
        return {"uid": uid, "name": "db"} if uid == 1 else {"uid": "broken"}

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
