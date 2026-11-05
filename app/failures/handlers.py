import logging

from fastapi import Request, Response
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException

from app.config.base import TEXT_ENCODING
from app.config.failures import FailureCode, FailureSettings
from app.config.settings import Settings
from app.logger.decorators import log_debug
from app.models import FailureBody


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
    return Response(
        content=body.model_dump_json(exclude_none=True).encode(encoding=TEXT_ENCODING),
        status_code=code.status_code,
        headers={
            settings.forwarding.content_type_header: settings.failures.content_type,
            settings.failures.error_header: code.error_code,
        },
    )
