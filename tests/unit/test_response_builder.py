import json

import pytest
from jsonschema.protocols import Validator
from pydantic import JsonValue

from app.config.failures import FailureSettings
from app.errors import ResponseRejectedError
from app.field_paths import FieldPath
from app.models import Answer
from app.response_builder import build_response
from app.rules import ResponseRules
from tests.support.rules import DRAFT_04, RULES, validator_of

DATABASE_SCHEMA: dict[str, JsonValue] = {
    "$schema": DRAFT_04,
    "type": "object",
    "properties": {"uid": {"type": "integer"}, "name": {"type": "string"}},
    "required": ["uid"],
    "additionalProperties": False,
}
SCHEMA: Validator = validator_of(schema=DATABASE_SCHEMA)
DEEP_BODY: bytes = b"[" * 100_000 + b"]" * 100_000
NESTED_LISTS_SCHEMA: Validator = validator_of(
    schema={"$schema": DRAFT_04, "type": "array", "items": {"$ref": "#"}}
)
BODY_TOO_DEEP_TO_VALIDATE: bytes = b"[" * 400 + b"]" * 400
IGNORE_INTERNAL: tuple[FieldPath, ...] = (("internal",),)


def rules_ignoring(*, ignored_fields: tuple[FieldPath, ...]) -> ResponseRules:
    return ResponseRules(
        schema_validator=SCHEMA,
        ignored_fields=ignored_fields,
        redacted_fields=(),
        error_limits=RULES.error_limits,
    )


def build(*, content: bytes, ignored_fields: tuple[FieldPath, ...] = ()) -> Answer:
    return build_response(
        target_response=Answer(status_code=200, headers={"x-answer": "1"}, content=content),
        rules=rules_ignoring(ignored_fields=ignored_fields),
        settings=FailureSettings(),
    )


def test_empty_body_is_returned_as_is() -> None:
    empty: Answer = Answer(status_code=204)

    assert (
        build_response(
            target_response=empty, rules=rules_ignoring(ignored_fields=()), settings=FailureSettings()
        )
        is empty
    )


def test_valid_body_is_returned_byte_for_byte() -> None:
    assert build(content=b'{"uid":1,  "name":"db"}').content == b'{"uid":1,  "name":"db"}'


@pytest.mark.parametrize("content", [b"<html>", b"\xff", b'{"a":"\xff"}'])
def test_non_json_body_is_rejected_at_the_root(content: bytes) -> None:
    with pytest.raises(ResponseRejectedError) as raised:
        build(content=content)

    assert raised.value.field == "$"


def test_non_json_body_is_rejected_with_the_configured_rule() -> None:
    with pytest.raises(ResponseRejectedError) as raised:
        build(content=b"<html>")

    assert raised.value.rule == "not_json"


def test_schema_violation_is_rejected_with_the_failing_field() -> None:
    with pytest.raises(ResponseRejectedError) as raised:
        build(content=b'{"uid": "one"}')

    assert raised.value.field == "$.uid"


def test_ignored_field_no_longer_breaks_the_schema() -> None:
    built: Answer = build(content=b'{"uid": 1, "internal": 5}', ignored_fields=IGNORE_INTERNAL)

    assert json.loads(s=built.content) == {"uid": 1}


def test_removing_a_field_keeps_the_status() -> None:
    assert build(content=b'{"uid": 1, "internal": 5}', ignored_fields=IGNORE_INTERNAL).status_code == 200


def test_removing_a_field_keeps_the_headers() -> None:
    built: Answer = build(content=b'{"uid": 1, "internal": 5}', ignored_fields=IGNORE_INTERNAL)

    assert built.headers == {"x-answer": "1"}


@pytest.mark.parametrize("content", [b'{"uid": NaN}', b'{"uid": Infinity}', b'{"uid": -Infinity}'])
def test_non_standard_number_is_rejected_as_not_json(content: bytes) -> None:
    with pytest.raises(ResponseRejectedError) as raised:
        build(content=content)

    assert raised.value.rule == "not_json"


def test_deeply_nested_body_is_rejected() -> None:
    with pytest.raises(ResponseRejectedError):
        build(content=DEEP_BODY, ignored_fields=IGNORE_INTERNAL)


def test_body_too_deep_to_validate_is_rejected() -> None:
    rules: ResponseRules = RULES.model_copy(update={"schema_validator": NESTED_LISTS_SCHEMA})

    with pytest.raises(ResponseRejectedError) as raised:
        build_response(
            target_response=Answer(status_code=200, content=BODY_TOO_DEEP_TO_VALIDATE),
            rules=rules,
            settings=FailureSettings(),
        )

    assert raised.value.rule == "too_deep"
