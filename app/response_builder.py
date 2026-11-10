import json

from pydantic import JsonValue

from app.config.constants import TEXT_ENCODING
from app.errors import ResponseRejectedError
from app.field_paths import ROOT, remove_fields
from app.logger.decorators import log_debug
from app.models import ClusterResponse
from app.rules import ResponseRules
from app.schema import validate_body


@log_debug
def build_response(*, cluster_response: ClusterResponse, rules: ResponseRules) -> ClusterResponse:
    if not cluster_response.content:
        return cluster_response
    try:
        body: JsonValue = json.loads(s=cluster_response.content)
    except (json.JSONDecodeError, UnicodeDecodeError) as error:
        raise ResponseRejectedError(field=ROOT, reason=f"the response body is not JSON: {error}") from error
    cleaned: JsonValue = remove_fields(body=body, field_paths=rules.ignored_fields)
    validate_body(body=cleaned, schema=rules.schema_validator)
    if cleaned == body:
        return cluster_response
    return cluster_response.model_copy(
        update={"content": json.dumps(obj=cleaned, ensure_ascii=False).encode(encoding=TEXT_ENCODING)}
    )
