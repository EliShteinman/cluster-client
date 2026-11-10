import pytest

from app import cluster_client
from tests.support.fake_cluster_api import FakeClusterApi


@pytest.fixture
def fake_cluster(monkeypatch: pytest.MonkeyPatch) -> FakeClusterApi:
    fake: FakeClusterApi = FakeClusterApi()
    monkeypatch.setattr(target=cluster_client.requests, name="request", value=fake.request)
    return fake
