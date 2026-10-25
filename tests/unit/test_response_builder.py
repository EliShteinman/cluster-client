import json

import pytest
from jsonschema import Draft202012Validator

from app.errors import ResponseRejectedError
from app.field_paths import FieldPath
from app.models import ClusterResponse
from app.response_builder import build_response
from tests.support.schemas import DATABASE_SCHEMA

SCHEMA: Draft202012Validator = Draft202012Validator(schema=DATABASE_SCHEMA)
IGNORE_INTERNAL: tuple[FieldPath, ...] = (("internal",),)


def build(*, content: bytes, ignored_fields: tuple[FieldPath, ...] = ()) -> ClusterResponse:
    return build_response(
        cluster_response=ClusterResponse(status_code=200, headers={"x-cluster": "1"}, content=content),
        schema=SCHEMA,
        ignored_fields=ignored_fields,
    )


def test_empty_body_is_returned_as_is() -> None:
    empty: ClusterResponse = ClusterResponse(status_code=204)

    assert build_response(cluster_response=empty, schema=SCHEMA, ignored_fields=()) is empty


def test_valid_body_is_returned_byte_for_byte() -> None:
    assert build(content=b'{"uid":1,  "name":"db"}').content == b'{"uid":1,  "name":"db"}'


def test_non_json_body_is_rejected_at_the_root() -> None:
    with pytest.raises(ResponseRejectedError) as raised:
        build(content=b"<html>")

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
