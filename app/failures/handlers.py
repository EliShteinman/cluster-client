import logging

from fastapi import Request, Response
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException

from app.config.failures import FailureCode, FailureSettings
from app.config.settings import Settings
from app.failures.response import own_answer
from app.logger.decorators import log_debug
from app.models import ClusterResponse, FailureBody


@log_debug
def refused_request_response(request: Request, error: HTTPException) -> Response:
    settings: FailureSettings = request.app.state.settings.failures
    return JSONResponse(
        status_code=error.status_code,
        content={"detail": error.detail},
        headers={**(error.headers or {}), settings.error_header: settings.invalid_request.error_code},
    )


@log_debug
def internal_error_response(request: Request, error: Exception) -> Response:
    settings: Settings = request.app.state.settings
    code: FailureCode = settings.failures.internal_error
    body: FailureBody = FailureBody(error=code.error_code, reason=type(error).__name__)
    logging.getLogger(name=settings.log.failure_file.logger_name).error(msg=f"{body.error}: {body.reason}")
    answer: ClusterResponse = own_answer(code=code, body=body, settings=settings)
    return Response(content=answer.content, status_code=answer.status_code, headers=answer.headers)
