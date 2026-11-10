from typing import ClassVar

from jsonschema import Draft202012Validator
from pydantic import ConfigDict

from app.config.validation import ValidationSettings
from app.field_paths import FieldPath, load_field_paths
from app.logger.decorators import log_debug
from app.models import FrozenModel
from app.schema import load_schema


class ResponseRules(FrozenModel):
    model_config: ClassVar[ConfigDict] = ConfigDict(arbitrary_types_allowed=True)

    schema_validator: Draft202012Validator
    ignored_fields: tuple[FieldPath, ...]
    redacted_fields: tuple[FieldPath, ...]


@log_debug
def load_rules(*, settings: ValidationSettings) -> ResponseRules:
    return ResponseRules(
        schema_validator=load_schema(path=settings.schema_path),
        ignored_fields=load_field_paths(path=settings.ignored_fields_path),
        redacted_fields=load_field_paths(path=settings.redacted_fields_path),
    )
