# pyright: reportUnknownMemberType=false, reportUnknownVariableType=false, reportUnknownArgumentType=false
import logging
from collections.abc import Iterable
from pathlib import Path

from jsonschema.exceptions import SchemaError, ValidationError, best_match, relevance
from jsonschema.protocols import Validator
from jsonschema.validators import validator_for
from pydantic import JsonValue

from app.errors import ResponseRejectedError, SchemaLoadError
from app.field_paths import FieldPath, remove_fields
from app.json_file import read_json_file
from app.logger.decorators import log_debug, log_info


@log_info(inputs=("path",))
@log_debug
def load_schema(*, path: Path) -> Validator:
    schema: JsonValue = read_json_file(path=path, error=SchemaLoadError)
    if not isinstance(schema, dict):
        raise SchemaLoadError(path=path, reason="the schema must be a JSON object")
    validator_class: type[Validator] = validator_for(schema=schema)
    try:
        validator_class.check_schema(schema=schema)
    except SchemaError as error:
        raise SchemaLoadError(path=path, reason=error.message) from error
    return validator_class(schema=schema)


@log_debug
def validate_body(
    *,
    body: JsonValue,
    schema: Validator,
    redacted_fields: tuple[FieldPath, ...],
    redacted_reason: str,
) -> None:
    error: ValidationError | None = best_match(errors=schema.iter_errors(instance=body))
    if error is None:
        return
    logging.getLogger(name=__name__).debug(msg=f"{error.json_path} breaks the schema: {error.message}")
    redacted_error: ValidationError | None = violation_at(
        body=remove_fields(body=body, field_paths=redacted_fields), schema=schema, json_path=error.json_path
    )
    raise ResponseRejectedError(
        rule=str(object=error.validator),
        field=error.json_path,
        reason=redacted_reason if redacted_error is None else redacted_error.message,
    )


@log_debug
def violation_at(*, body: JsonValue, schema: Validator, json_path: str) -> ValidationError | None:
    errors: list[ValidationError] = every_error(errors=schema.iter_errors(instance=body))
    at_path: list[ValidationError] = [error for error in errors if error.json_path == json_path]
    return max(at_path, key=relevance, default=None)


@log_debug
def every_error(*, errors: Iterable[ValidationError]) -> list[ValidationError]:
    return [found for error in errors for found in (error, *every_error(errors=error.context or ()))]


@log_debug
def first_violation(*, body: JsonValue, schema: Validator) -> str | None:
    error: ValidationError | None = best_match(errors=schema.iter_errors(instance=body))
    return None if error is None else f"{error.json_path}: {error.message}"
