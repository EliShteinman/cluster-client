import json

import pytest
from jsonschema import Draft202012Validator
from pydantic import JsonValue

from app.errors import ResponseRejectedError
from app.field_paths import FieldPath
from app.models import ClusterResponse
from app.response_builder import build_response
from app.rules import ResponseRules

DATABASE_SCHEMA: dict[str, JsonValue] = {
    "$schema": "https://json-schema.org/draft/2020-12/schema",
    "type": "object",
    "properties": {"uid": {"type": "integer"}, "name": {"type": "string"}},
    "required": ["uid"],
    "additionalProperties": False,
}
SCHEMA: Draft202012Validator = Draft202012Validator(schema=DATABASE_SCHEMA)
IGNORE_INTERNAL: tuple[FieldPath, ...] = (("internal",),)


def rules_ignoring(*, ignored_fields: tuple[FieldPath, ...]) -> ResponseRules:
    return ResponseRules(schema_validator=SCHEMA, ignored_fields=ignored_fields, redacted_fields=())


def build(*, content: bytes, ignored_fields: tuple[FieldPath, ...] = ()) -> ClusterResponse:
    return build_response(
        cluster_response=ClusterResponse(status_code=200, headers={"x-cluster": "1"}, content=content),
        rules=rules_ignoring(ignored_fields=ignored_fields),
    )


def test_empty_body_is_returned_as_is() -> None:
    empty: ClusterResponse = ClusterResponse(status_code=204)

    assert build_response(cluster_response=empty, rules=rules_ignoring(ignored_fields=())) is empty


def test_valid_body_is_returned_byte_for_byte() -> None:
    assert build(content=b'{"uid":1,  "name":"db"}').content == b'{"uid":1,  "name":"db"}'


@pytest.mark.parametrize("content", [b"<html>", b"\xff", b'{"a":"\xff"}'])
def test_non_json_body_is_rejected_at_the_root(content: bytes) -> None:
    with pytest.raises(ResponseRejectedError) as raised:
        build(content=content)

    assert raised.value.field == "$"


def test_schema_violation_is_rejected_with_the_failing_field() -> None:
    with pytest.raises(ResponseRejectedError) as raised:
        build(content=b'{"uid": "one"}')

    assert raised.value.field == "$.uid"


def test_ignored_field_no_longer_breaks_the_schema() -> None:
    built: ClusterResponse = build(content=b'{"uid": 1, "internal": 5}', ignored_fields=IGNORE_INTERNAL)

    assert json.loads(s=built.content) == {"uid": 1}


def test_removing_a_field_keeps_status_and_headers() -> None:
    built: ClusterResponse = build(content=b'{"uid": 1, "internal": 5}', ignored_fields=IGNORE_INTERNAL)

    assert (built.status_code, built.headers) == (200, {"x-cluster": "1"})
