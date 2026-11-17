import re
from pathlib import Path

from pydantic import JsonValue, TypeAdapter, ValidationError

from app.errors import FieldPathsLoadError
from app.json_reading import read_json_file
from app.logger.decorators import log_debug, log_info

ROOT: str = "$"
ALL_ITEMS: str = "[*]"
SEGMENT_PATTERN: re.Pattern[str] = re.compile(pattern=r"\.([^.\[\]]+)|(\[\*\])")

FIELD_PATH_LIST: TypeAdapter[list[str]] = TypeAdapter(type=list[str])

type FieldPath = tuple[str, ...]


@log_info(inputs=("path",))
@log_debug
def load_field_paths(*, path: Path) -> tuple[FieldPath, ...]:
    paths: JsonValue = read_json_file(path=path, error=FieldPathsLoadError)
    try:
        fields: list[str] = FIELD_PATH_LIST.validate_python(paths, strict=True)
    except ValidationError:
        raise FieldPathsLoadError(path=path, reason="the file must be a JSON list of field paths") from None
    field_paths: tuple[FieldPath, ...] = tuple(parse_field_path(field=field, path=path) for field in fields)
    if any(field_path[-1] == ALL_ITEMS for field_path in field_paths):
        raise FieldPathsLoadError(path=path, reason=f"a field path must name a field, not end in {ALL_ITEMS}")
    return field_paths


def parse_field_path(*, field: str, path: Path) -> FieldPath:
    if not field.startswith(ROOT):
        raise FieldPathsLoadError(path=path, reason=f"{field} must start with {ROOT}")
    rest: str = field.removeprefix(ROOT)
    matches: list[re.Match[str]] = list(SEGMENT_PATTERN.finditer(string=rest))
    if "".join(match.group(0) for match in matches) != rest or not matches:
        raise FieldPathsLoadError(path=path, reason=f"{field} must be a field path, like $.a[*].b")
    return tuple(match.group(1) or ALL_ITEMS for match in matches)


@log_debug
def remove_fields(*, body: JsonValue, field_paths: tuple[FieldPath, ...]) -> JsonValue:
    cleaned: JsonValue = body
    for field_path in field_paths:
        cleaned = without_field(node=cleaned, field_path=field_path)
    return cleaned


def without_field(*, node: JsonValue, field_path: FieldPath) -> JsonValue:
    head: str = field_path[0]
    rest: FieldPath = field_path[1:]
    if head == ALL_ITEMS:
        return without_field_in_items(node=node, field_path=rest)
    if not isinstance(node, dict) or head not in node:
        return node
    if not rest:
        return {key: value for key, value in node.items() if key != head}
    child: JsonValue = without_field(node=node[head], field_path=rest)
    return node if child is node[head] else {**node, head: child}


def without_field_in_items(*, node: JsonValue, field_path: FieldPath) -> JsonValue:
    if not isinstance(node, list):
        return node
    items: list[JsonValue] = [without_field(node=item, field_path=field_path) for item in node]
    unchanged: bool = all(new is old for new, old in zip(items, node, strict=True))
    return node if unchanged else items
