# pyright: reportUnknownMemberType=false, reportUnknownVariableType=false, reportUnknownArgumentType=false
from pathlib import Path

from jsonschema import Draft202012Validator
from jsonschema.exceptions import SchemaError, ValidationError, best_match
from pydantic import JsonValue

from app.errors import ResponseRejectedError, SchemaLoadError
from app.json_file import read_json_file
from app.logger.decorators import log_debug, log_info


@log_info(inputs=("path",))
@log_debug
def load_schema(*, path: Path) -> Draft202012Validator:
    schema: JsonValue = read_json_file(path=path, error=SchemaLoadError)
    if not isinstance(schema, dict):
        raise SchemaLoadError(path=path, reason="the schema must be a JSON object")
    try:
        Draft202012Validator.check_schema(schema=schema)
    except SchemaError as error:
        raise SchemaLoadError(path=path, reason=error.message) from error
    return Draft202012Validator(schema=schema)


@log_debug
def validate_body(*, body: JsonValue, schema: Draft202012Validator) -> None:
    error: ValidationError | None = best_match(errors=schema.iter_errors(instance=body))
    if error is not None:
        raise ResponseRejectedError(field=error.json_path, reason=error.message)
