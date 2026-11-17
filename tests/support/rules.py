from pathlib import Path

from jsonschema.protocols import Validator
from jsonschema.validators import validator_for
from pydantic import JsonValue

from app.config.validation import ValidationSettings
from app.rules import ResponseRules, load_rules

FILES: Path = Path(__file__).parents[2] / "helm" / "files"
SAMPLES: Path = Path(__file__).parent / "cluster_samples"
DRAFT_04: str = "http://json-schema.org/draft-04/schema#"
RULES: ResponseRules = load_rules(
    settings=ValidationSettings(
        schema_path=FILES / "response-schema.json",
        ignored_fields_path=FILES / "ignored-fields.json",
        redacted_fields_path=FILES / "redacted-fields.json",
    )
)


def validator_of(*, schema: dict[str, JsonValue]) -> Validator:
    return validator_for(schema=schema)(schema=schema)
