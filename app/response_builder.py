import json

from jsonschema import Draft202012Validator
from pydantic import JsonValue

from app.config import TEXT_ENCODING
from app.errors import ResponseRejectedError
from app.ignored_fields import ROOT, FieldPath, remove_ignored_fields
from app.logger import log_debug
from app.models import ClusterResponse
from app.schema import validate_body


@log_debug
def build_response(
    *, cluster_response: ClusterResponse, schema: Draft202012Validator, ignored_fields: tuple[FieldPath, ...]
) -> ClusterResponse:
    if not cluster_response.content:
        return cluster_response
    original_body: JsonValue = decode_body(content=cluster_response.content)
    body: JsonValue = remove_ignored_fields(body=original_body, ignored_fields=ignored_fields)
    validate_body(body=body, schema=schema)
    if body == original_body:
        return cluster_response
    return cluster_response.model_copy(update={"content": encode_body(body=body)})


@log_debug
def decode_body(*, content: bytes) -> JsonValue:
    try:
        return json.loads(s=content)
    except json.JSONDecodeError as error:
        raise ResponseRejectedError(
            field=ROOT, reason=f"the response body is not JSON: {error.msg}"
        ) from error


@log_debug
def encode_body(*, body: JsonValue) -> bytes:
    return json.dumps(obj=body, ensure_ascii=False).encode(encoding=TEXT_ENCODING)
