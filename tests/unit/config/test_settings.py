import pytest
from pydantic import ValidationError

from app.config.failures import FailureSettings
from app.config.settings import NoEnvFileSettings


def test_one_env_value_keeps_the_other_defaults_of_its_section(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("CLUSTER_CLIENT_FAILURES__REJECTED__STATUS_CODE", "503")

    assert NoEnvFileSettings().failures.rejected.error_code == "response_rejected"


@pytest.mark.parametrize(
    "values",
    [
        {"unsent_characters_message": "{count} left {unknown}"},
        {"not_json_reason": "not JSON: {unknown}"},
        {"unsent_characters_message": "{count}" + "x" * 512},
        {"shortened_field_prefix": "." * 512},
    ],
    ids=["unknown unsent placeholder", "unknown not-JSON placeholder", "long unsent message", "long prefix"],
)
def test_failure_texts_that_cannot_pass_the_firewall_are_refused(values: dict[str, str]) -> None:
    with pytest.raises(ValidationError):
        FailureSettings.model_validate(obj=values)
