import json
from pathlib import Path

from pydantic import JsonValue

DATABASE_SCHEMA: dict[str, JsonValue] = {
    "$schema": "https://json-schema.org/draft/2020-12/schema",
    "type": "object",
    "properties": {"uid": {"type": "integer"}, "name": {"type": "string"}},
    "required": ["uid"],
    "additionalProperties": False,
}


def write_schema(*, path: Path, schema: dict[str, JsonValue]) -> Path:
    path.write_text(json.dumps(schema), encoding="utf-8")
    return path
