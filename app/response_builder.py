import json

from pydantic import JsonValue

from app.config.constants import TEXT_ENCODING
from app.config.failures import FailureSettings
from app.errors import ResponseRejectedError
from app.field_paths import ROOT, remove_fields
from app.json_file import read_json_body
from app.logger.decorators import log_debug
from app.models import TargetResponse
from app.rules import ResponseRules
from app.schema import validate_body


@log_debug
def build_response(
    *, target_response: TargetResponse, rules: ResponseRules, settings: FailureSettings
) -> TargetResponse:
    if not target_response.content:
        return target_response
    try:
        body: JsonValue = read_json_body(content=target_response.content)
    except ValueError as error:
        raise ResponseRejectedError(
            rule=settings.not_json_rule, field=ROOT, reason=settings.not_json_reason.format(error=error)
        ) from error
    except RecursionError as error:
        raise too_deep(settings=settings) from error
    try:
        cleaned: JsonValue = remove_fields(body=body, field_paths=rules.ignored_fields)
        validate_body(
            body=cleaned,
            schema=rules.schema_validator,
            redacted_fields=rules.redacted_fields,
            redacted_reason=settings.redacted_reason,
        )
    except RecursionError as error:
        raise too_deep(settings=settings) from error
    if cleaned is body:
        return target_response
    return target_response.model_copy(
        update={"content": json.dumps(obj=cleaned, ensure_ascii=False).encode(encoding=TEXT_ENCODING)}
    )


@log_debug
def too_deep(*, settings: FailureSettings) -> ResponseRejectedError:
    return ResponseRejectedError(rule=settings.too_deep_rule, field=ROOT, reason=settings.too_deep_reason)
