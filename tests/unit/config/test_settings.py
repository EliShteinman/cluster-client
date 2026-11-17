import pytest
from pydantic import ValidationError

from app.config.failures import FailureSettings


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
