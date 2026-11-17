import re
from pathlib import Path

from pydantic import JsonValue

from app.errors import FieldPathsLoadError
from app.json_file import read_json_file
from app.logger.decorators import log_debug, log_info

ROOT: str = "$"
ALL_ITEMS: str = "[*]"
SEGMENT_PATTERN: re.Pattern[str] = re.compile(pattern=r"\.([^.\[\]]+)|(\[\*\])")

type FieldPath = tuple[str, ...]


@log_info(inputs=("path",))
@log_debug
def load_field_paths(*, path: Path) -> tuple[FieldPath, ...]:
    paths: JsonValue = read_json_file(path=path, error=FieldPathsLoadError)
    fields: list[str] = (
        [field for field in paths if isinstance(field, str)] if isinstance(paths, list) else []
    )
    if not isinstance(paths, list) or len(fields) != len(paths):
        raise FieldPathsLoadError(path=path, reason="the file must be a JSON list of field paths")
    return tuple(parse_field_path(field=field, path=path) for field in fields)


@log_debug
def parse_field_path(*, field: str, path: Path) -> FieldPath:
    if not field.startswith(ROOT):
        raise FieldPathsLoadError(path=path, reason=f"{field} must start with {ROOT}")
    rest: str = field.removeprefix(ROOT)
    matches: list[re.Match[str]] = list(SEGMENT_PATTERN.finditer(string=rest))
    if "".join(match.group(0) for match in matches) != rest or not matches or matches[-1].group(2):
        raise FieldPathsLoadError(path=path, reason=f"{field} must name a field, like $.a[*].b")
    return tuple(match.group(1) or ALL_ITEMS for match in matches)


@log_debug
def remove_fields(*, body: JsonValue, field_paths: tuple[FieldPath, ...]) -> JsonValue:
    cleaned: JsonValue = body
    for field_path in field_paths:
        cleaned = without_field(node=cleaned, field_path=field_path)
    return cleaned


@log_debug
def without_field(*, node: JsonValue, field_path: FieldPath) -> JsonValue:
    head, *rest = field_path
    if head == ALL_ITEMS:
        return without_field_in_items(node=node, field_path=tuple(rest))
    if not isinstance(node, dict) or head not in node:
        return node
    if not rest:
        return {key: value for key, value in node.items() if key != head}
    child: JsonValue = without_field(node=node[head], field_path=tuple(rest))
    return node if child is node[head] else {**node, head: child}


@log_debug
def without_field_in_items(*, node: JsonValue, field_path: FieldPath) -> JsonValue:
    if not isinstance(node, list):
        return node
    items: list[JsonValue] = [without_field(node=item, field_path=field_path) for item in node]
    unchanged: bool = all(new is old for new, old in zip(items, node, strict=True))
    return node if unchanged else items
