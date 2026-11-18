import json
import logging
import traceback

from fastapi import Request, Response
from starlette.exceptions import HTTPException

from app.access import login_challenge
from app.config.failures import FailureCode
from app.config.settings import Settings
from app.errors import AccessDeniedError
from app.failures.answers import logged_answer
from app.logger.decorators import log_debug
from app.models import Answer, FailureDetails
from app.rules.response_rules import ResponseRules
from app.state import rules_of, settings_of


@log_debug
def reason_text(*, detail: object) -> str:
    return detail if isinstance(detail, str) else json.dumps(obj=detail, ensure_ascii=False, default=str)


@log_debug
def refused_request_response(request: Request, error: HTTPException) -> Response:
    settings: Settings = settings_of(state=request.app.state)
    answer: Answer = own_failure_answer(
        request=request,
        code=settings.failures.invalid_request,
        reason=reason_text(detail=error.detail),
        level=logging.WARNING,
    )
    return Response(
        content=answer.content,
        status_code=error.status_code,
        headers={**(error.headers or {}), **answer.headers},
    )


@log_debug
def access_denied_response(request: Request, error: AccessDeniedError) -> Response:
    settings: Settings = settings_of(state=request.app.state)
    answer: Answer = own_failure_answer(
        request=request, code=settings.failures.unauthorized, reason=str(object=error), level=logging.WARNING
    )
    challenge: dict[str, str] = {settings.access.challenge_header: login_challenge(settings=settings.access)}
    return Response(
        content=answer.content, status_code=answer.status_code, headers={**answer.headers, **challenge}
    )


@log_debug
def internal_error_response(request: Request, error: Exception) -> Response:
    settings: Settings = settings_of(state=request.app.state)
    answer: Answer = own_failure_answer(
        request=request,
        code=settings.failures.internal_error,
        reason="".join(traceback.format_exception(error)),
        level=logging.ERROR,
    )
    return Response(content=answer.content, status_code=answer.status_code, headers=answer.headers)


@log_debug
def own_failure_answer(*, request: Request, code: FailureCode, reason: str, level: int) -> Answer:
    settings: Settings = settings_of(state=request.app.state)
    rules: ResponseRules = rules_of(state=request.app.state)
    return logged_answer(
        code=code,
        details=FailureDetails(error=code.error_code, reason=reason),
        message=f"{code.error_code}: {reason}",
        level=level,
        limits=rules.error_limits,
        settings=settings,
        extra_headers={},
    )
