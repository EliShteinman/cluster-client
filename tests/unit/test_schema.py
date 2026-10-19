import json
from pathlib import Path

import pytest

from app.errors import ResponseRejectedError, SchemaLoadError
from app.schema import load_schema, validate_body
from tests.support.schemas import DATABASE_SCHEMA, write_schema


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


def test_loaded_schema_accepts_a_matching_body(schema_path: Path) -> None:
    validate_body(body={"uid": 1}, schema=load_schema(path=schema_path))


def test_violation_names_the_failing_field(tmp_path: Path) -> None:
    schema_path: Path = write_schema(path=tmp_path / "schema.json", schema=DATABASE_SCHEMA)

    with pytest.raises(ResponseRejectedError) as raised:
        validate_body(body={"uid": "one"}, schema=load_schema(path=schema_path))

    assert raised.value.field == "$.uid"
