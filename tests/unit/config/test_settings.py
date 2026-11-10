import pytest

from app.config.settings import NoEnvFileSettings


def test_one_env_value_keeps_the_other_defaults_of_its_section(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("CLUSTER_CLIENT_FAILURES__REJECTED__STATUS_CODE", "503")

    assert NoEnvFileSettings().failures.rejected.error_code == "response_rejected"
