import logging
import traceback

from fastapi import Request, Response
from starlette.exceptions import HTTPException

from app.config.failures import FailureCode
from app.config.settings import Settings
from app.failures.response import failure_body, own_answer
from app.logger.decorators import log_debug
from app.models import ClusterResponse, FailureDetails


@log_debug
def refused_request_response(request: Request, error: HTTPException) -> Response:
    settings: Settings = request.app.state.settings
    code: FailureCode = settings.failures.invalid_request
    details: FailureDetails = FailureDetails(error=code.error_code, reason=str(object=error.detail))
    logging.getLogger(name=settings.log.failure_file.logger_name).warning(
        msg=f"{details.error}: {details.reason}", extra=details.model_dump(mode="json")
    )
    answer: ClusterResponse = own_answer(
        code=code, body=failure_body(details=details, settings=settings.failures), settings=settings
    )
    return Response(
        content=answer.content,
        status_code=error.status_code,
        headers={**(error.headers or {}), **answer.headers},
    )


@log_debug
def internal_error_response(request: Request, error: Exception) -> Response:
    settings: Settings = request.app.state.settings
    code: FailureCode = settings.failures.internal_error
    details: FailureDetails = FailureDetails(
        error=code.error_code, reason="".join(traceback.format_exception(error))
    )
    logging.getLogger(name=settings.log.failure_file.logger_name).error(
        msg=f"{details.error}: {details.reason}", extra=details.model_dump(mode="json")
    )
    answer: ClusterResponse = own_answer(
        code=code, body=failure_body(details=details, settings=settings.failures), settings=settings
    )
    return Response(content=answer.content, status_code=answer.status_code, headers=answer.headers)
