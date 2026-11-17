import pytest
from pydantic import JsonValue

from app.errors import SchemaLoadError
from app.models import ErrorBodyLimits
from app.schema_limits import error_body_limits
from tests.support.rules import SCHEMA_PATH, error_body_schema


def limits_of(*, schema: dict[str, JsonValue]) -> ErrorBodyLimits:
    return error_body_limits(schema=schema, path=SCHEMA_PATH)


@pytest.mark.parametrize(
    ("limit", "expected"),
    [("error_length", 40), ("rule_length", 41), ("field_length", 42), ("part_length", 60), ("max_parts", 5)],
)
def test_each_limit_is_read_from_its_field(limit: str, expected: int) -> None:
    assert getattr(limits_of(schema=error_body_schema(changed={})), limit) == expected


def test_the_smallest_limit_of_several_branches_is_taken() -> None:
    field: dict[str, JsonValue] = {"anyOf": [{"maxLength": 30}, {"maxLength": 20}]}

    assert limits_of(schema=error_body_schema(changed={"field": field})).field_length == 20


def test_a_limit_is_found_through_a_reference() -> None:
    schema: dict[str, JsonValue] = {
        **error_body_schema(changed={"field": {"$ref": "#/definitions/text"}}),
        "definitions": {"text": {"maxLength": 25}},
    }

    assert limits_of(schema=schema).field_length == 25


def test_a_limit_is_found_through_pattern_properties() -> None:
    schema: dict[str, JsonValue] = {
        **error_body_schema(changed={}),
        "properties": {},
        "patternProperties": {"^[a-z]+$": {"maxLength": 35, "maxItems": 4, "items": {"maxLength": 35}}},
    }

    assert limits_of(schema=schema).max_parts == 4


@pytest.mark.parametrize(
    "changed",
    [
        {"field": {}},
        {"reason": {"items": {"maxLength": 60}}},
        {"reason": {"maxItems": 5}},
        {"field": {"$ref": "#"}},
    ],
    ids=["no field limit", "no item count", "no part length", "reference to the root"],
)
def test_a_field_without_a_limit_stops_the_start(changed: dict[str, JsonValue]) -> None:
    with pytest.raises(SchemaLoadError, match="no max"):
        limits_of(schema=error_body_schema(changed=changed))


def test_a_schema_that_refers_to_itself_stops_the_start() -> None:
    schema: dict[str, JsonValue] = {
        **error_body_schema(changed={"field": {"$ref": "#/definitions/loop"}}),
        "definitions": {"loop": {"anyOf": [{"$ref": "#/definitions/loop"}]}},
    }

    with pytest.raises(SchemaLoadError, match="refers to itself"):
        limits_of(schema=schema)
