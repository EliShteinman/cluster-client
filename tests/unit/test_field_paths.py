import json
from pathlib import Path

import pytest
from pydantic import JsonValue

from app.errors import FieldPathsLoadError
from app.field_paths import ALL_ITEMS, FieldPath, load_field_paths, remove_fields

DATABASES: list[JsonValue] = [
    {"uid": 1, "shards_placement": "dense", "endpoints": [{"internal_id": 5, "port": 12000}]},
    {"uid": 2},
]


def write(*, tmp_path: Path, content: str) -> Path:
    path: Path = tmp_path / "field-paths.json"
    path.write_text(data=content, encoding="utf-8")
    return path


def test_paths_are_read_from_the_file(tmp_path: Path) -> None:
    path: Path = write(tmp_path=tmp_path, content=json.dumps(obj=["$[*].endpoints[*].internal_id"]))

    assert load_field_paths(path=path) == ((ALL_ITEMS, "endpoints", ALL_ITEMS, "internal_id"),)


@pytest.mark.parametrize(
    "content",
    [
        "not json",
        json.dumps(obj={"a": 1}),
        json.dumps(obj=["a.b"]),
        json.dumps(obj=["$[*]"]),
        json.dumps(obj=["$.a[0].b"]),
    ],
    ids=["not json", "not a list", "no root", "ends in [*]", "item index"],
)
def test_unusable_file_is_reported(tmp_path: Path, content: str) -> None:
    with pytest.raises(FieldPathsLoadError, match=r"field-paths\.json"):
        load_field_paths(path=write(tmp_path=tmp_path, content=content))


def test_missing_file_is_reported(tmp_path: Path) -> None:
    with pytest.raises(FieldPathsLoadError):
        load_field_paths(path=tmp_path / "missing.json")


@pytest.mark.parametrize(
    ("field_path", "expected"),
    [
        (
            (ALL_ITEMS, "shards_placement"),
            [{"uid": 1, "endpoints": [{"internal_id": 5, "port": 12000}]}, {"uid": 2}],
        ),
        (
            (ALL_ITEMS, "endpoints", ALL_ITEMS, "internal_id"),
            [{"uid": 1, "shards_placement": "dense", "endpoints": [{"port": 12000}]}, {"uid": 2}],
        ),
        ((ALL_ITEMS, "no_such_field"), DATABASES),
    ],
    ids=["field in every item", "nested field", "absent field"],
)
def test_only_the_named_field_is_removed(field_path: FieldPath, expected: list[JsonValue]) -> None:
    assert remove_fields(body=DATABASES, field_paths=(field_path,)) == expected


def test_the_original_body_is_left_untouched() -> None:
    remove_fields(body=DATABASES, field_paths=((ALL_ITEMS, "shards_placement"),))

    assert DATABASES[0]["shards_placement"] == "dense"
