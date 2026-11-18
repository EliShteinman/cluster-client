import pytest

from app.target import client
from tests.support.fake_target_api import FakeTargetApi


@pytest.fixture
def fake_target(monkeypatch: pytest.MonkeyPatch) -> FakeTargetApi:
    fake: FakeTargetApi = FakeTargetApi()
    monkeypatch.setattr(target=client.requests, name="request", value=fake.request)
    return fake
