import json
import logging

from pydantic import JsonValue

from app.config.base import TEXT_ENCODING
from app.config.failures import FailureSettings
from app.config.settings import Settings
from app.errors import RequestFailedError
from app.failures.codes import failure_code
from app.field_paths import FieldPath, remove_fields
from app.logger.decorators import log_debug
from app.models import ClusterRequest, ClusterResponse, RequestFailure


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
