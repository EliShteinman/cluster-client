import json
import logging

from pydantic import JsonValue

from app.config import TEXT_ENCODING, FailureCode, FailureSettings, Settings
from app.errors import ConnectionFailedError, NoResponseError, RequestFailedError
from app.field_paths import FieldPath, remove_fields
from app.logger import log_debug
from app.models import ClusterRequest, ClusterResponse, FailureBody, RequestFailure


@log_debug
def failure_code(*, failure: RequestFailedError, settings: FailureSettings) -> FailureCode:
    if isinstance(failure, ConnectionFailedError):
        return settings.connection_failed
    if isinstance(failure, NoResponseError):
        return settings.no_response
    return settings.rejected


@log_debug
def record_failure(
    *,
    request: ClusterRequest,
    failure: RequestFailedError,
    cluster_response: ClusterResponse | None,
    redacted_fields: tuple[FieldPath, ...],
    settings: Settings,
) -> None:
    record: RequestFailure = failure_record(
        request=request,
        failure=failure,
        cluster_response=cluster_response,
        redacted_fields=redacted_fields,
        settings=settings.failures,
    )
    logging.getLogger(name=settings.log.failure_file.logger_name).warning(
        msg=f"{record.error}: {record.method} {record.url} {record.reason}",
        extra=record.model_dump(mode="json"),
    )


@log_debug
def failure_record(
    *,
    request: ClusterRequest,
    failure: RequestFailedError,
    cluster_response: ClusterResponse | None,
    redacted_fields: tuple[FieldPath, ...],
    settings: FailureSettings,
) -> RequestFailure:
    record: RequestFailure = RequestFailure(
        error=failure_code(failure=failure, settings=settings).error_code,
        reason=failure.reason,
        field=failure.field,
        method=request.method,
        url=str(request.url),
    )
    if cluster_response is None:
        return record
    return record.model_copy(
        update={
            "cluster_status_code": cluster_response.status_code,
            "cluster_response": redacted_content(
                content=cluster_response.content, redacted_fields=redacted_fields
            ),
        }
    )


@log_debug
def redacted_content(*, content: bytes, redacted_fields: tuple[FieldPath, ...]) -> str:
    text: str = content.decode(encoding=TEXT_ENCODING, errors="replace")
    try:
        body: JsonValue = json.loads(s=text)
    except json.JSONDecodeError:
        return text
    redacted: JsonValue = remove_fields(body=body, field_paths=redacted_fields)
    return text if redacted == body else json.dumps(obj=redacted, ensure_ascii=False)


@log_debug
def failure_response(
    *, failure: RequestFailedError, cluster_response: ClusterResponse | None, settings: Settings
) -> ClusterResponse:
    code: FailureCode = failure_code(failure=failure, settings=settings.failures)
    body: FailureBody = FailureBody(error=code.error_code, reason=failure.reason, field=failure.field)
    headers: dict[str, str] = {
        settings.forwarding.content_type_header: settings.failures.content_type,
        settings.failures.error_header: code.error_code,
    }
    if cluster_response is not None:
        headers[settings.failures.cluster_status_header] = str(cluster_response.status_code)
    return ClusterResponse(
        status_code=code.status_code,
        headers=headers,
        content=body.model_dump_json(exclude_none=True).encode(encoding=TEXT_ENCODING),
    )
