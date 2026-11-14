from app.config.constants import TEXT_ENCODING
from app.config.failures import FailureCode, FailureSettings
from app.config.settings import Settings
from app.errors import RequestFailedError
from app.failures.codes import failure_code
from app.failures.reason_parts import reason_parts, shortened_field
from app.logger.decorators import log_debug
from app.models import ClusterResponse, FailureBody, FailureDetails


@log_debug
def failure_response(
    *, failure: RequestFailedError, cluster_response: ClusterResponse | None, settings: Settings
) -> ClusterResponse:
    code: FailureCode = failure_code(failure=failure, settings=settings.failures)
    answer: ClusterResponse = own_answer(
        code=code,
        body=failure_body(
            details=failure_details(error_code=code.error_code, failure=failure), settings=settings.failures
        ),
        settings=settings,
    )
    if cluster_response is None:
        return answer
    cluster_status: dict[str, str] = {
        settings.failures.cluster_status_header: str(cluster_response.status_code)
    }
    return answer.model_copy(update={"headers": {**answer.headers, **cluster_status}})


@log_debug
def failure_details(*, error_code: str, failure: RequestFailedError) -> FailureDetails:
    return FailureDetails(error=error_code, rule=failure.rule, field=failure.field, reason=failure.reason)


@log_debug
def failure_body(*, details: FailureDetails, settings: FailureSettings) -> FailureBody:
    return FailureBody(
        error=details.error,
        rule=details.rule,
        field=shortened_field(field=details.field, settings=settings),
        reason=reason_parts(text=details.reason, settings=settings),
    )


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
