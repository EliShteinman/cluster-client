import pytest

from app import target_client
from tests.support.fake_target_api import FakeTargetApi


@pytest.fixture
def fake_target(monkeypatch: pytest.MonkeyPatch) -> FakeTargetApi:
    fake: FakeTargetApi = FakeTargetApi()
    monkeypatch.setattr(target=target_client.requests, name="request", value=fake.request)
    return fake
