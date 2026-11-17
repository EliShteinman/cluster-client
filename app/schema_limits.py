import re

from pydantic import JsonValue

from app.logger.decorators import log_debug, log_info
from app.models import ErrorBodyLimits

ITEMS: None = None
LOCAL_REFERENCE_PREFIX: str = "#/"
BRANCH_KEYWORDS: tuple[str, ...] = ("anyOf", "oneOf", "allOf")

type SchemaNode = dict[str, JsonValue]
type SchemaStep = str | None


@log_info(outputs=("part_length", "max_parts", "field_length"))
@log_debug
def error_body_limits(*, schema: JsonValue) -> ErrorBodyLimits:
    if not isinstance(schema, dict):
        return ErrorBodyLimits(
            error_length=None, rule_length=None, field_length=None, part_length=None, max_parts=None
        )
    return ErrorBodyLimits(
        error_length=smallest_limit(schema=schema, path=("error",), keyword="maxLength"),
        rule_length=smallest_limit(schema=schema, path=("rule",), keyword="maxLength"),
        field_length=smallest_limit(schema=schema, path=("field",), keyword="maxLength"),
        part_length=smallest_limit(schema=schema, path=("reason", ITEMS), keyword="maxLength"),
        max_parts=smallest_limit(schema=schema, path=("reason",), keyword="maxItems"),
    )


@log_debug
def smallest_limit(*, schema: SchemaNode, path: tuple[SchemaStep, ...], keyword: str) -> int | None:
    limits: list[int] = [
        limit for node in nodes_at(schema=schema, path=path) if isinstance(limit := node.get(keyword), int)
    ]
    return min(limits, default=None)


@log_debug
def nodes_at(*, schema: SchemaNode, path: tuple[SchemaStep, ...]) -> list[SchemaNode]:
    nodes: list[SchemaNode] = expanded(schema=schema, node=schema)
    for step in path:
        nodes = [
            found
            for node in nodes
            for child in children(node=node, step=step)
            for found in expanded(schema=schema, node=child)
        ]
    return nodes


@log_debug
def expanded(*, schema: SchemaNode, node: SchemaNode) -> list[SchemaNode]:
    found: list[SchemaNode] = [node]
    reference: JsonValue = node.get("$ref")
    if isinstance(reference, str):
        found += expanded(schema=schema, node=referenced(schema=schema, reference=reference))
    for keyword in BRANCH_KEYWORDS:
        for branch in schema_list(value=node.get(keyword)):
            found += expanded(schema=schema, node=branch)
    return found


@log_debug
def referenced(*, schema: SchemaNode, reference: str) -> SchemaNode:
    if not reference.startswith(LOCAL_REFERENCE_PREFIX):
        return {}
    node: JsonValue = schema
    for part in reference.removeprefix(LOCAL_REFERENCE_PREFIX).split(sep="/"):
        node = node.get(part.replace("~1", "/").replace("~0", "~")) if isinstance(node, dict) else None
    return node if isinstance(node, dict) else {}


@log_debug
def children(*, node: SchemaNode, step: SchemaStep) -> list[SchemaNode]:
    if step is None:
        return item_schemas(node=node)
    return property_schemas(node=node, name=step)


@log_debug
def property_schemas(*, node: SchemaNode, name: str) -> list[SchemaNode]:
    named: JsonValue = schema_of(value=node.get("properties"), key=name)
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


@log_debug
def item_schemas(*, node: SchemaNode) -> list[SchemaNode]:
    items: JsonValue = node.get("items")
    if isinstance(items, dict):
        return [items]
    additional: JsonValue = node.get("additionalItems")
    return [
        *schema_list(value=items),
        *schema_list(value=node.get("prefixItems")),
        *([additional] if isinstance(additional, dict) else []),
    ]


@log_debug
def schema_of(*, value: JsonValue, key: str) -> JsonValue:
    return value.get(key) if isinstance(value, dict) else None


@log_debug
def schema_list(*, value: JsonValue) -> list[SchemaNode]:
    return [item for item in value if isinstance(item, dict)] if isinstance(value, list) else []
