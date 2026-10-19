from collections.abc import Iterator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app import cluster_client
from app.config import Settings
from app.logger import configure_logging, reset_logging
from app.main import create_app
from tests.support.app_settings import make_app_settings
from tests.support.fake_cluster_api import FakeClusterApi
from tests.support.logging_settings import JsonLines, json_file_settings, read_json_lines
from tests.support.schemas import DATABASE_SCHEMA, write_schema

TESTS_ROOT: Path = Path(__file__).parent
TEST_TIERS: frozenset[str] = frozenset({"unit", "integration", "e2e"})


def pytest_collection_modifyitems(items: list[pytest.Item]) -> None:
    for item in items:
        tier: str = item.path.relative_to(TESTS_ROOT).parts[0]
        if tier in TEST_TIERS:
            item.add_marker(getattr(pytest.mark, tier))


@pytest.fixture(autouse=True)
def clean_logging() -> Iterator[None]:
    yield
    reset_logging()


@pytest.fixture
def log_path(tmp_path: Path) -> Path:
    return tmp_path / "app.log"


@pytest.fixture
def failure_log_path(tmp_path: Path) -> Path:
    return tmp_path / "failures.log"


@pytest.fixture
def schema_path(tmp_path: Path) -> Path:
    return write_schema(path=tmp_path / "schema.json", schema=DATABASE_SCHEMA)


@pytest.fixture
def json_lines(log_path: Path, failure_log_path: Path) -> JsonLines:
    configure_logging(settings=json_file_settings(log_path=log_path, failure_log_path=failure_log_path))
    return lambda: read_json_lines(log_path=log_path)


@pytest.fixture
def failure_lines(failure_log_path: Path) -> JsonLines:
    return lambda: read_json_lines(log_path=failure_log_path)


@pytest.fixture
def app_settings(log_path: Path, failure_log_path: Path, schema_path: Path) -> Settings:
    return make_app_settings(log_path=log_path, failure_log_path=failure_log_path, schema_path=schema_path)


@pytest.fixture
def fake_cluster(monkeypatch: pytest.MonkeyPatch) -> FakeClusterApi:
    fake: FakeClusterApi = FakeClusterApi()
    monkeypatch.setattr(target=cluster_client.requests, name="request", value=fake.request)
    return fake


@pytest.fixture
def client(app_settings: Settings, fake_cluster: FakeClusterApi) -> Iterator[TestClient]:
    with TestClient(app=create_app(settings=app_settings)) as test_client:
        yield test_client
