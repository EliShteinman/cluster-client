import copy
import json
import re
from pathlib import Path

from pydantic import JsonValue

from app.config import TEXT_ENCODING
from app.errors import FieldPathsLoadError
from app.logger import log_debug, log_info

ROOT: str = "$"
ALL_ITEMS: str = "[*]"
SEGMENT_PATTERN: re.Pattern[str] = re.compile(pattern=r"\.([^.\[\]]+)|(\[\*\])")

type FieldPath = tuple[str, ...]


@log_info(inputs=("path",))
@log_debug
def load_field_paths(*, path: Path) -> tuple[FieldPath, ...]:
    try:
        paths: JsonValue = json.loads(s=path.read_text(encoding=TEXT_ENCODING))
    except (OSError, json.JSONDecodeError) as error:
        raise FieldPathsLoadError(path=path, reason=str(error)) from error
    if not isinstance(paths, list) or not all(isinstance(field, str) for field in paths):
        raise FieldPathsLoadError(path=path, reason="the file must be a JSON list of field paths")
    return tuple(parse_field_path(field=field, path=path) for field in paths)


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
    if not field_paths:
        return body
    cleaned: JsonValue = copy.deepcopy(body)
    for field_path in field_paths:
        remove_field(node=cleaned, field_path=field_path)
    return cleaned


@log_debug
def remove_field(*, node: JsonValue, field_path: FieldPath) -> None:
    head, *rest = field_path
    if head == ALL_ITEMS:
        children: list[JsonValue] = node if isinstance(node, list) else []
    elif isinstance(node, dict) and head in node:
        if not rest:
            del node[head]
            return
        children = [node[head]]
    else:
        return
    for child in children:
        remove_field(node=child, field_path=tuple(rest))
