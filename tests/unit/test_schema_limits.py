import pytest
from pydantic import JsonValue

from app.models import ErrorBodyLimits
from app.schema_limits import error_body_limits
from tests.support.rules import RULES

TWO_BRANCHES: dict[str, JsonValue] = {
    "anyOf": [
        {"properties": {"field": {"maxLength": 40}}},
        {"properties": {"field": {"maxLength": 30}}},
    ]
}


@pytest.mark.parametrize(
    ("limit", "expected"),
    [
        ("error_length", 256),
        ("rule_length", 256),
        ("field_length", 256),
        ("part_length", 256),
        ("max_parts", 500),
    ],
)
def test_limits_are_read_from_the_firewall_schema(limit: str, expected: int) -> None:
    assert getattr(RULES.error_limits, limit) == expected


def test_the_smallest_limit_of_several_branches_is_taken() -> None:
    assert error_body_limits(schema=TWO_BRANCHES).field_length == 30


def test_a_field_without_a_limit_has_none() -> None:
    limits: ErrorBodyLimits = error_body_limits(schema=TWO_BRANCHES)

    assert limits.part_length is None
