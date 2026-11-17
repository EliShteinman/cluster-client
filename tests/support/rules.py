from pathlib import Path

from jsonschema.protocols import Validator
from jsonschema.validators import validator_for
from pydantic import JsonValue

from app.config.validation import ValidationSettings
from app.rules import ResponseRules, load_rules

FILES: Path = Path(__file__).parents[2] / "helm" / "files"
SAMPLES: Path = Path(__file__).parent / "cluster_samples"
SCHEMA_PATH: Path = FILES / "response-schema.json"
DRAFT_04: str = "http://json-schema.org/draft-04/schema#"
ERROR_BODY_PROPERTIES: dict[str, JsonValue] = {
    "error": {"maxLength": 40},
    "rule": {"maxLength": 41},
    "field": {"maxLength": 42},
    "reason": {"maxItems": 5, "items": {"maxLength": 60}},
}
RULES: ResponseRules = load_rules(
    settings=ValidationSettings(
        schema_path=SCHEMA_PATH,
        ignored_fields_path=FILES / "ignored-fields.json",
        redacted_fields_path=FILES / "redacted-fields.json",
    )
)


def validator_of(*, schema: dict[str, JsonValue]) -> Validator:
    return validator_for(schema=schema)(schema=schema)


def error_body_schema(*, changed: dict[str, JsonValue]) -> dict[str, JsonValue]:
    return {"$schema": DRAFT_04, "properties": {**ERROR_BODY_PROPERTIES, **changed}}
