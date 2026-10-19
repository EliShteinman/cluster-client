import json
from pathlib import Path

from jsonschema import Draft202012Validator
from jsonschema.exceptions import SchemaError, ValidationError, best_match
from pydantic import JsonValue

from app.config import TEXT_ENCODING
from app.errors import ResponseRejectedError, SchemaLoadError
from app.logger import log_debug, log_info


@log_info(inputs=("path",))
@log_debug
def load_schema(*, path: Path) -> Draft202012Validator:
    schema: JsonValue = read_schema_file(path=path)
    if not isinstance(schema, dict):
        raise SchemaLoadError(path=path, reason="the schema must be a JSON object")
    try:
        Draft202012Validator.check_schema(schema=schema)
    except SchemaError as error:
        raise SchemaLoadError(path=path, reason=error.message) from error
    return Draft202012Validator(schema=schema)


@log_debug
def read_schema_file(*, path: Path) -> JsonValue:
    try:
        return json.loads(s=path.read_text(encoding=TEXT_ENCODING))
    except (OSError, json.JSONDecodeError) as error:
        raise SchemaLoadError(path=path, reason=str(error)) from error


@log_debug
def validate_body(*, body: JsonValue, schema: Draft202012Validator) -> None:
    error: ValidationError | None = best_match(errors=schema.iter_errors(instance=body))
    if error is not None:
        raise ResponseRejectedError(field=error.json_path, reason=error.message)
