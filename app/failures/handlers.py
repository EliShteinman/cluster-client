import logging
import traceback

from fastapi import Request, Response
from starlette.exceptions import HTTPException

from app.config.failures import FailureCode
from app.config.settings import Settings
from app.errors import AccessDeniedError
from app.failures.answers import logged_answer
from app.logger.decorators import log_debug
from app.models import FailureDetails, TargetResponse
from app.rules import ResponseRules


@log_debug
def refused_request_response(request: Request, error: HTTPException) -> Response:
    settings: Settings = request.app.state.settings
    answer: TargetResponse = own_failure_answer(
        request=request,
        code=settings.failures.invalid_request,
        reason=str(object=error.detail),
        level=logging.WARNING,
    )
    return Response(
        content=answer.content,
        status_code=error.status_code,
        headers={**(error.headers or {}), **answer.headers},
    )


@log_debug
def access_denied_response(request: Request, error: AccessDeniedError) -> Response:
    settings: Settings = request.app.state.settings
    answer: TargetResponse = own_failure_answer(
        request=request, code=settings.failures.unauthorized, reason=str(object=error), level=logging.WARNING
    )
    challenge: dict[str, str] = {
        settings.access.challenge_header: f'{settings.access.scheme} realm="{settings.access.realm}"'
    }
    return Response(
        content=answer.content, status_code=answer.status_code, headers={**answer.headers, **challenge}
    )


@log_debug
def internal_error_response(request: Request, error: Exception) -> Response:
    settings: Settings = request.app.state.settings
    answer: TargetResponse = own_failure_answer(
        request=request,
        code=settings.failures.internal_error,
        reason="".join(traceback.format_exception(error)),
        level=logging.ERROR,
    )
    return Response(content=answer.content, status_code=answer.status_code, headers=answer.headers)


@log_debug
def own_failure_answer(*, request: Request, code: FailureCode, reason: str, level: int) -> TargetResponse:
    settings: Settings = request.app.state.settings
    rules: ResponseRules = request.app.state.rules
    return logged_answer(
        code=code,
        details=FailureDetails(error=code.error_code, reason=reason),
        message=f"{code.error_code}: {reason}",
        level=level,
        limits=rules.error_limits,
        settings=settings,
        extra_headers={},
    )
