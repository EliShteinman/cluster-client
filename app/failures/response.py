from app.config import TEXT_ENCODING, FailureCode, Settings
from app.errors import RequestFailedError
from app.failures.codes import failure_code
from app.logger import log_debug
from app.models import ClusterResponse, FailureBody


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
