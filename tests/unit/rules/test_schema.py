import json
from pathlib import Path

import pytest
from jsonschema.protocols import Validator
from pydantic import JsonValue

from app.errors import ResponseRejectedError, SchemaLoadError
from app.rules.field_paths import FieldPath
from app.rules.schema import load_schema, validate_body
from tests.support.rules import DRAFT_04, validator_of


@pytest.mark.parametrize(
    "content",
    [None, "not json", "[1, 2]", json.dumps({"type": "no-such-type"})],
    ids=["missing file", "not json", "not an object", "invalid schema"],
)
def test_unusable_schema_file_is_reported(tmp_path: Path, content: str | None) -> None:
    path: Path = tmp_path / "schema.json"
    if content is not None:
        path.write_text(data=content, encoding="utf-8")

    with pytest.raises(SchemaLoadError, match=r"schema\.json"):
        load_schema(path=path)


REDACTED_FIELD: str = "authentication_admin_pass"
REDACT_FIELD: tuple[FieldPath, ...] = ((REDACTED_FIELD,),)
REDACTED_REASON: str = "the failing value is a redacted field"
FIELD_SCHEMA: Validator = validator_of(
    schema={
        "$schema": DRAFT_04,
        "type": "object",
        "properties": {REDACTED_FIELD: {"type": "string", "maxLength": 3}, "acl_uid": {"type": "integer"}},
        "maxProperties": 2,
    }
)


TIED_FAILURES_SCHEMA: Validator = validator_of(
    schema={"$schema": DRAFT_04, "maxProperties": 2, "required": ["uid"]}
)
NESTED_ANY_OF_SCHEMA: Validator = validator_of(
    schema={
        "$schema": DRAFT_04,
        "anyOf": [
            {
                "properties": {
                    "config": {
                        "maxProperties": 2,
                        "additionalProperties": False,
                        "patternProperties": {"^[a-z_]+$": {}},
                    }
                }
            }
        ],
    }
)


def rejection(
    *,
    body: JsonValue,
    schema: Validator = FIELD_SCHEMA,
    redacted_fields: tuple[FieldPath, ...] = REDACT_FIELD,
) -> ResponseRejectedError:
    with pytest.raises(ResponseRejectedError) as raised:
        validate_body(
            body=body,
            schema=schema,
            redacted_fields=redacted_fields,
            redacted_reason=REDACTED_REASON,
        )
    return raised.value


def test_failing_password_is_named_as_the_field() -> None:
    assert rejection(body={REDACTED_FIELD: "TOPSECRET"}).field == f"$.{REDACTED_FIELD}"


def test_failing_password_keeps_its_rule() -> None:
    assert rejection(body={REDACTED_FIELD: "TOPSECRET"}).rule == "maxLength"


def test_failing_password_is_explained_without_its_value() -> None:
    assert rejection(body={REDACTED_FIELD: "TOPSECRET"}).reason == REDACTED_REASON


def test_field_is_the_failure_that_blocked_the_answer() -> None:
    assert rejection(body={REDACTED_FIELD: 5, "acl_uid": "one"}).field == f"$.{REDACTED_FIELD}"


def test_reason_of_a_failing_password_ignores_other_failures() -> None:
    assert rejection(body={REDACTED_FIELD: 5, "acl_uid": "one"}).reason == REDACTED_REASON


def test_rule_is_the_failure_that_blocked_the_answer() -> None:
    body: JsonValue = {REDACTED_FIELD: "x", "name": "db", "port": 1}

    assert rejection(body=body, schema=TIED_FAILURES_SCHEMA).rule == "maxProperties"


def test_any_of_failure_is_explained_from_the_redacted_copy() -> None:
    body: JsonValue = {"config": {"name": "db", REDACTED_FIELD: "x", "bad key": 1}}

    redacted_fields: tuple[FieldPath, ...] = (("config", REDACTED_FIELD),)

    assert (
        "bad key" in rejection(body=body, schema=NESTED_ANY_OF_SCHEMA, redacted_fields=redacted_fields).reason
    )


def test_reason_is_built_without_the_redacted_fields() -> None:
    body: JsonValue = {REDACTED_FIELD: "abc", "uid": 1, "name": "db", "port": 1}

    assert "abc" not in rejection(body=body).reason


def test_unknown_secret_stays_in_the_reason() -> None:
    body: JsonValue = {"uid": 1, "name": "db", "new_pass": "TOPSECRET"}

    assert "TOPSECRET" in rejection(body=body).reason
