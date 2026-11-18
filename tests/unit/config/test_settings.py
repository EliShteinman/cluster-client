import pytest
from pydantic import ValidationError

from app.config.failures import FailureSettings
from app.config.forwarding import ForwardingSettings
from app.config.headers import HeaderSettings


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


def test_a_refused_reason_with_an_unknown_placeholder_is_refused() -> None:
    with pytest.raises(ValidationError):
        HeaderSettings(refused_reason="{headers} and {unknown}")


@pytest.mark.parametrize("connect_timeout_seconds", [28.0, 30.0], ids=["equal", "longer"])
def test_a_connect_timeout_not_shorter_than_the_total_is_refused(connect_timeout_seconds: float) -> None:
    with pytest.raises(ValidationError):
        ForwardingSettings(connect_timeout_seconds=connect_timeout_seconds, timeout_seconds=28.0)
