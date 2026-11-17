import re
from pathlib import Path

from pydantic import JsonValue

from app.errors import SchemaLoadError
from app.field_paths import ALL_ITEMS, FieldPath, parse_field_path
from app.logger.decorators import log_debug, log_info
from app.models import ErrorBodyLimits

LOCAL_REFERENCE_PREFIX: str = "#/"
BRANCH_KEYWORDS: tuple[str, ...] = ("anyOf", "oneOf", "allOf")

type SchemaNode = dict[str, JsonValue]


@log_info(outputs=("error_length", "rule_length", "field_length", "part_length", "max_parts"))
@log_debug
def error_body_limits(*, schema: SchemaNode, path: Path) -> ErrorBodyLimits:
    try:
        return ErrorBodyLimits(
            error_length=smallest_limit(schema=schema, field="$.error", keyword="maxLength", path=path),
            rule_length=smallest_limit(schema=schema, field="$.rule", keyword="maxLength", path=path),
            field_length=smallest_limit(schema=schema, field="$.field", keyword="maxLength", path=path),
            part_length=smallest_limit(schema=schema, field="$.reason[*]", keyword="maxLength", path=path),
            max_parts=smallest_limit(schema=schema, field="$.reason", keyword="maxItems", path=path),
        )
    except RecursionError as error:
        raise SchemaLoadError(path=path, reason="the schema refers to itself") from error


@log_debug
def smallest_limit(*, schema: SchemaNode, field: str, keyword: str, path: Path) -> int:
    field_path: FieldPath = parse_field_path(field=field, path=path)
    limits: list[int] = [
        limit
        for node in nodes_at(schema=schema, field_path=field_path)
        if isinstance(limit := node.get(keyword), int)
    ]
    if not limits:
        raise SchemaLoadError(path=path, reason=f"no {keyword} for {field}, the error body needs one")
    return min(limits)


@log_debug
def nodes_at(*, schema: SchemaNode, field_path: FieldPath) -> list[SchemaNode]:
    nodes: list[SchemaNode] = with_alternatives(schema=schema, node=schema)
    for step in field_path:
        nodes = [
            found
            for node in nodes
            for child in children(node=node, step=step)
            for found in with_alternatives(schema=schema, node=child)
        ]
    return nodes


def with_alternatives(*, schema: SchemaNode, node: SchemaNode) -> list[SchemaNode]:
    found: list[SchemaNode] = [node]
    reference: JsonValue = node.get("$ref")
    if isinstance(reference, str):
        found += with_alternatives(schema=schema, node=referenced(schema=schema, reference=reference))
    for keyword in BRANCH_KEYWORDS:
        for branch in schema_list(value=node.get(keyword)):
            found += with_alternatives(schema=schema, node=branch)
    return found


def referenced(*, schema: SchemaNode, reference: str) -> SchemaNode:
    if not reference.startswith(LOCAL_REFERENCE_PREFIX):
        return {}
    node: JsonValue = schema
    for part in reference.removeprefix(LOCAL_REFERENCE_PREFIX).split(sep="/"):
        node = node.get(part.replace("~1", "/").replace("~0", "~")) if isinstance(node, dict) else None
    return node if isinstance(node, dict) else {}


def children(*, node: SchemaNode, step: str) -> list[SchemaNode]:
    if step == ALL_ITEMS:
        return item_schemas(node=node)
    return property_schemas(node=node, name=step)


def property_schemas(*, node: SchemaNode, name: str) -> list[SchemaNode]:
    properties: JsonValue = node.get("properties")
    named: JsonValue = properties.get(name) if isinstance(properties, dict) else None
    patterns: JsonValue = node.get("patternProperties")
    pattern_schemas: dict[str, JsonValue] = patterns if isinstance(patterns, dict) else {}
    matching: list[SchemaNode] = [
        child
        for pattern, child in pattern_schemas.items()
        if isinstance(child, dict) and re.search(pattern=pattern, string=name)
    ]
    found: list[SchemaNode] = ([named] if isinstance(named, dict) else []) + matching
    additional: JsonValue = node.get("additionalProperties")
    return found or ([additional] if isinstance(additional, dict) else [])


def item_schemas(*, node: SchemaNode) -> list[SchemaNode]:
    items: JsonValue = node.get("items")
    if isinstance(items, dict):
        return [items]
    additional: JsonValue = node.get("additionalItems")
    return [
        *schema_list(value=items),
        *([additional] if isinstance(additional, dict) else []),
    ]


def schema_list(*, value: JsonValue) -> list[SchemaNode]:
    return [item for item in value if isinstance(item, dict)] if isinstance(value, list) else []
