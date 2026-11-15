import logging
import traceback

from fastapi import Request, Response
from starlette.exceptions import HTTPException

from app.config.failures import FailureCode
from app.config.settings import Settings
from app.errors import AccessDeniedError
from app.failures.response import failure_body, own_answer
from app.logger.decorators import log_debug
from app.models import ClusterResponse, FailureDetails


@log_debug
def refused_request_response(request: Request, error: HTTPException) -> Response:
    settings: Settings = request.app.state.settings
    answer: ClusterResponse = logged_answer(
        code=settings.failures.invalid_request,
        reason=str(object=error.detail),
        level=logging.WARNING,
        settings=settings,
    )
    return Response(
        content=answer.content,
        status_code=error.status_code,
        headers={**(error.headers or {}), **answer.headers},
    )


@log_debug
def access_denied_response(request: Request, error: AccessDeniedError) -> Response:
    settings: Settings = request.app.state.settings
    answer: ClusterResponse = logged_answer(
        code=settings.failures.unauthorized,
        reason=str(object=error),
        level=logging.WARNING,
        settings=settings,
    )
    challenge: dict[str, str] = {
        settings.access.challenge_header: f'{settings.access.scheme} realm="{settings.access.realm}"'
    }
    return Response(
        content=answer.content, status_code=answer.status_code, headers={**answer.headers, **challenge}
    )


@log_debug
def logged_answer(*, code: FailureCode, reason: str, level: int, settings: Settings) -> ClusterResponse:
    details: FailureDetails = FailureDetails(error=code.error_code, reason=reason)
    logging.getLogger(name=settings.log.failure_file.logger_name).log(
        level=level, msg=f"{details.error}: {details.reason}", extra=details.model_dump(mode="json")
    )
    return own_answer(
        code=code, body=failure_body(details=details, settings=settings.failures), settings=settings
    )


@log_debug
def internal_error_response(request: Request, error: Exception) -> Response:
    settings: Settings = request.app.state.settings
    answer: ClusterResponse = logged_answer(
        code=settings.failures.internal_error,
        reason="".join(traceback.format_exception(error)),
        level=logging.ERROR,
        settings=settings,
    )
    return Response(content=answer.content, status_code=answer.status_code, headers=answer.headers)
