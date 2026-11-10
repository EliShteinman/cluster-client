import json
from pathlib import Path

import pytest

from app.errors import SchemaLoadError
from app.schema import load_schema


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
