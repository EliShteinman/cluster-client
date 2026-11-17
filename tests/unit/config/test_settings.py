from pathlib import Path

import pytest
from pydantic import ValidationError

from app.config.failures import FailureSettings
from app.config.headers import HeaderSettings
from app.config.settings import NoEnvFileSettings
from tests.support.access import ACCESS


def test_one_env_value_keeps_the_other_defaults_of_its_section(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("CLUSTER_CLIENT_FAILURES__REJECTED__STATUS_CODE", "503")

    assert NoEnvFileSettings(access=ACCESS).failures.rejected.error_code == "response_rejected"


@pytest.mark.parametrize(
    "values",
    [
        {"unsent_characters_message": "{count} left {unknown}"},
        {"not_json_reason": "not JSON: {unknown}"},
    ],
    ids=["unknown unsent placeholder", "unknown not-JSON placeholder"],
)
def test_failure_texts_with_unknown_placeholders_are_refused(values: dict[str, str]) -> None:
    with pytest.raises(ValidationError):
        FailureSettings.model_validate(obj=values)


def test_a_flat_env_var_does_not_change_a_section(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("CLUSTER_CLIENT_URL", "x-flat-url")

    assert NoEnvFileSettings(access=ACCESS).headers.url == HeaderSettings().url


def test_settings_without_env_file_ignore_it_in_every_section(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    (tmp_path / ".env").write_text(
        data="CLUSTER_CLIENT_HEADERS__URL=x-from-file\nCLUSTER_CLIENT_URL=x-flat\n"
    )
    monkeypatch.chdir(tmp_path)

    assert NoEnvFileSettings(access=ACCESS).headers.url == HeaderSettings().url
