from typing import Annotated

from fastapi import APIRouter, Depends, Request, Response, Security

from app.access import check_access
from app.config.settings import Settings
from app.errors import RequestFailedError
from app.failures.answers import failed_request_answer
from app.logger.decorators import log_debug, log_info
from app.models import Answer, TargetRequest
from app.response_builder import build_response
from app.routes.read_request import read_body, read_target_request
from app.routes.target_openapi import BasicAuthDocumentation, failure_responses, request_documentation
from app.rules import ResponseRules
from app.target_client import send_to_target


@log_debug
def build_target_router(*, settings: Settings) -> APIRouter:
    router: APIRouter = APIRouter()
    router.add_api_route(
        path="/",
        endpoint=target_endpoint,
        methods=["POST"],
        response_description=(
            "The target's own answer: its status, headers and body. The ignored fields are removed from "
            "the body (then re-encoded); the headers the server recomputes and any "
            f"{settings.forwarding.edge_header_prefix}* header of the target are not returned"
        ),
        responses=failure_responses(settings=settings),
        openapi_extra=request_documentation(settings=settings),
        dependencies=[
            Depends(dependency=require_access),
            Security(
                dependency=BasicAuthDocumentation(
                    scheme_name="manager",
                    description="The manager's username and password, checked on every call",
                )
            ),
        ],
    )
    return router


@log_debug
def require_access(*, request: Request) -> None:
    settings: Settings = request.app.state.settings
    check_access(header_value=request.headers.get(settings.access.header, ""), settings=settings.access)


@log_info(outputs=("status_code",))
@log_debug
def target_endpoint(*, request: Request, body: Annotated[bytes, Depends(dependency=read_body)]) -> Response:
    settings: Settings = request.app.state.settings
    rules: ResponseRules = request.app.state.rules
    target_request: TargetRequest = read_target_request(
        headers=dict(request.headers), body=body, settings=settings
    )
    target_response: Answer | None = None
    try:
        target_response = send_to_target(request=target_request, settings=settings.forwarding)
        answer: Answer = build_response(
            target_response=target_response, rules=rules, settings=settings.failures
        )
    except RequestFailedError as failure:
        answer = failed_request_answer(
            request=target_request,
            failure=failure,
            target_response=target_response,
            rules=rules,
            settings=settings,
        )
    return Response(content=answer.content, status_code=answer.status_code, headers=answer.headers)
