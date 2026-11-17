import pytest
from jsonschema.protocols import Validator
from pydantic import JsonValue

from app.config.failures import FailureCode, FailureSettings
from app.config.settings import NoEnvFileSettings, Settings
from app.errors import SchemaLoadError
from app.failures.fit_check import check_own_answers
from app.rules import ResponseRules
from app.schema_limits import error_body_limits
from tests.support.access import ACCESS
from tests.support.rules import DRAFT_04, RULES, validator_of

SETTINGS: Settings = NoEnvFileSettings(access=ACCESS)


def rules_for(*, schema: dict[str, JsonValue]) -> ResponseRules:
    validator: Validator = validator_of(schema={"$schema": DRAFT_04, **schema})
    return RULES.model_copy(
        update={"schema_validator": validator, "error_limits": error_body_limits(schema=schema)}
    )


def strings_up_to(*, length: int) -> dict[str, JsonValue]:
    return {"properties": {"reason": {"items": {"maxLength": length}}}}


def test_the_firewall_schema_holds_every_own_answer() -> None:
    check_own_answers(rules=RULES, settings=SETTINGS)


@pytest.mark.parametrize(
    "schema",
    [
        {"additionalProperties": False, "properties": {"error": {}, "rule": {}, "field": {}}},
        strings_up_to(length=10),
        {"properties": {"error": {"maxLength": 5}}},
        {"properties": {"rule": {"maxLength": 5}}},
        {"properties": {"field": {"maxLength": 2}}},
        {"properties": {"reason": {"maxItems": 0}}},
    ],
    ids=[
        "no reason allowed",
        "unsent message too long",
        "error too long",
        "rule too long",
        "prefix too long",
        "no parts",
    ],
)
def test_a_schema_that_cannot_hold_an_own_answer_stops_the_start(schema: dict[str, JsonValue]) -> None:
    with pytest.raises(SchemaLoadError):
        check_own_answers(rules=rules_for(schema=schema), settings=SETTINGS)


def test_a_configured_error_code_must_fit_the_schema() -> None:
    settings: Settings = NoEnvFileSettings(
        access=ACCESS, failures=FailureSettings(rejected=FailureCode(status_code=502, error_code="r" * 300))
    )

    with pytest.raises(SchemaLoadError):
        check_own_answers(rules=RULES, settings=settings)
