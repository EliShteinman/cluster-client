import pytest
from jsonschema.protocols import Validator
from pydantic import JsonValue

from app.config.failures import FailureCode, FailureSettings
from app.config.settings import NoEnvFileSettings, Settings
from app.errors import SchemaLoadError
from app.failures.own_answers_check import check_own_answers
from app.rules.response_rules import ResponseRules
from app.rules.schema_limits import error_body_limits
from tests.support.access import ACCESS
from tests.support.rules import RULES, SCHEMA_PATH, error_body_schema, validator_of

SETTINGS: Settings = NoEnvFileSettings(access=ACCESS)


def rules_for(*, changed: dict[str, JsonValue]) -> ResponseRules:
    schema: dict[str, JsonValue] = error_body_schema(changed=changed)
    validator: Validator = validator_of(schema=schema)
    return RULES.model_copy(
        update={
            "schema_validator": validator,
            "error_limits": error_body_limits(schema=schema, path=SCHEMA_PATH),
        }
    )


def test_the_firewall_schema_holds_every_own_answer() -> None:
    check_own_answers(rules=RULES, settings=SETTINGS)


@pytest.mark.parametrize(
    "changed",
    [
        {"reason": {"type": "string", "maxItems": 5, "items": {"maxLength": 60}}},
        {"reason": {"maxItems": 5, "items": {"maxLength": 10}}},
        {"error": {"maxLength": 5}},
        {"rule": {"maxLength": 5}},
        {"field": {"maxLength": 2}},
        {"reason": {"maxItems": 0, "items": {"maxLength": 60}}},
    ],
    ids=[
        "reason not a list",
        "unsent message too long",
        "error too long",
        "rule too long",
        "prefix too long",
        "no parts",
    ],
)
def test_a_schema_that_cannot_hold_an_own_answer_stops_the_start(changed: dict[str, JsonValue]) -> None:
    rules: ResponseRules = rules_for(changed=changed)

    with pytest.raises(SchemaLoadError):
        check_own_answers(rules=rules, settings=SETTINGS)


def test_a_configured_error_code_must_fit_the_schema() -> None:
    settings: Settings = NoEnvFileSettings(
        access=ACCESS, failures=FailureSettings(rejected=FailureCode(status_code=502, error_code="r" * 300))
    )

    with pytest.raises(SchemaLoadError):
        check_own_answers(rules=RULES, settings=settings)
