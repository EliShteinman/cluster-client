from app.config.constants import TEXT_ENCODING
from app.config.failures import FailureCode
from app.config.settings import Settings
from app.errors import RequestFailedError
from app.failures.codes import failure_code
from app.logger.decorators import log_debug
from app.models import ClusterResponse, FailureBody


@log_debug
def failure_response(
    *, failure: RequestFailedError, cluster_response: ClusterResponse | None, settings: Settings
) -> ClusterResponse:
    code: FailureCode = failure_code(failure=failure, settings=settings.failures)
    answer: ClusterResponse = own_answer(
        code=code,
        body=FailureBody(error=code.error_code, reason=failure.reason, field=failure.field),
        settings=settings,
    )
    if cluster_response is None:
        return answer
    cluster_status: dict[str, str] = {
        settings.failures.cluster_status_header: str(cluster_response.status_code)
    }
    return answer.model_copy(update={"headers": {**answer.headers, **cluster_status}})


@log_debug
def own_answer(*, code: FailureCode, body: FailureBody, settings: Settings) -> ClusterResponse:
    return ClusterResponse(
        status_code=code.status_code,
        headers={
            settings.forwarding.content_type_header: settings.failures.content_type,
            settings.failures.error_header: code.error_code,
        },
        content=body.model_dump_json(exclude_none=True).encode(encoding=TEXT_ENCODING),
    )
