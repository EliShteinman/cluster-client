from typing import ClassVar, cast

from jsonschema.protocols import Validator
from pydantic import ConfigDict, JsonValue

from app.config.validation import ValidationSettings
from app.field_paths import FieldPath, load_field_paths
from app.logger.decorators import log_debug
from app.models import ErrorBodyLimits, FrozenModel
from app.schema import load_schema
from app.schema_limits import error_body_limits


class ResponseRules(FrozenModel):
    model_config: ClassVar[ConfigDict] = ConfigDict(arbitrary_types_allowed=True)

    schema_validator: Validator
    ignored_fields: tuple[FieldPath, ...]
    redacted_fields: tuple[FieldPath, ...]
    error_limits: ErrorBodyLimits


@log_debug
def load_rules(*, settings: ValidationSettings) -> ResponseRules:
    schema_validator: Validator = load_schema(path=settings.schema_path)
    return ResponseRules(
        schema_validator=schema_validator,
        ignored_fields=load_field_paths(path=settings.ignored_fields_path),
        redacted_fields=load_field_paths(path=settings.redacted_fields_path),
        error_limits=error_body_limits(
            schema=cast(typ=dict[str, JsonValue], val=schema_validator.schema), path=settings.schema_path
        ),
    )
