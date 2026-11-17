import json
import logging

from pydantic import JsonValue

from app.config.constants import TEXT_ENCODING
from app.config.failures import FailureCode, FailureSettings
from app.config.settings import Settings
from app.errors import ConnectionFailedError, InvalidTargetRequestError, NoResponseError, RequestFailedError
from app.failures.body import failure_body
from app.field_paths import FieldPath, remove_fields
from app.json_file import read_json_body
from app.logger.decorators import log_debug
from app.models import ErrorBodyLimits, FailureDetails, RequestFailure, TargetRequest, TargetResponse
from app.rules import ResponseRules


@log_debug
def failed_request_answer(
    *,
    request: TargetRequest,
    failure: RequestFailedError,
    target_response: TargetResponse | None,
    rules: ResponseRules,
    settings: Settings,
) -> TargetResponse:
    code: FailureCode = failure_code(failure=failure, settings=settings.failures)
    record: RequestFailure = request_failure(
        request=request,
        failure=failure,
        error_code=code.error_code,
        target_response=target_response,
        redacted_fields=rules.redacted_fields,
    )
    answer: TargetResponse = logged_answer(
        code=code,
        details=record,
        message=f"{record.error}: {record.method} {record.url} {record.reason}",
        level=logging.WARNING,
        limits=rules.error_limits,
        settings=settings,
    )
    if target_response is None:
        return answer
    target_status: dict[str, str] = {settings.failures.target_status_header: str(target_response.status_code)}
    return answer.model_copy(update={"headers": {**answer.headers, **target_status}})


@log_debug
def failure_code(*, failure: RequestFailedError, settings: FailureSettings) -> FailureCode:
    if isinstance(failure, InvalidTargetRequestError):
        return settings.invalid_request
    if isinstance(failure, ConnectionFailedError):
        return settings.connection_failed
    if isinstance(failure, NoResponseError):
        return settings.no_response
    return settings.rejected


@log_debug
def request_failure(
    *,
    request: TargetRequest,
    failure: RequestFailedError,
    error_code: str,
    target_response: TargetResponse | None,
    redacted_fields: tuple[FieldPath, ...],
) -> RequestFailure:
    record: RequestFailure = RequestFailure(
        error=error_code,
        rule=failure.rule,
        field=failure.field,
        reason=failure.reason,
        method=request.method,
        url=request.url,
    )
    if target_response is None:
        return record
    return record.model_copy(
        update={
            "target_status_code": target_response.status_code,
            "target_response": redacted_content(
                content=target_response.content, redacted_fields=redacted_fields
            ),
        }
    )


@log_debug
def redacted_content(*, content: bytes, redacted_fields: tuple[FieldPath, ...]) -> str:
    text: str = content.decode(encoding=TEXT_ENCODING, errors="replace")
    try:
        body: JsonValue = read_json_body(content=text)
        redacted: JsonValue = remove_fields(body=body, field_paths=redacted_fields)
    except ValueError, RecursionError:
        return text
    return text if redacted is body else json.dumps(obj=redacted, ensure_ascii=False)


@log_debug
def logged_answer(
    *,
    code: FailureCode,
    details: FailureDetails,
    message: str,
    level: int,
    limits: ErrorBodyLimits,
    settings: Settings,
) -> TargetResponse:
    logging.getLogger(name=settings.log.failure_file.logger_name).log(
        level=level, msg=message, extra=details.model_dump(mode="json")
    )
    return TargetResponse(
        status_code=code.status_code,
        headers={
            settings.failures.content_type_header: settings.failures.content_type,
            settings.failures.error_header: code.error_code,
        },
        content=failure_body(details=details, limits=limits, settings=settings.failures)
        .model_dump_json(exclude_none=True)
        .encode(encoding=TEXT_ENCODING),
    )
