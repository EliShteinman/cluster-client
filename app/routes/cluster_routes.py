from typing import Annotated

from fastapi import APIRouter, Depends, Request, Response

from app.cluster_client import send_to_cluster
from app.config.settings import Settings
from app.errors import RequestFailedError
from app.failures.log import record_failure
from app.failures.response import failure_response
from app.logger.decorators import log_debug, log_info
from app.models import ClusterRequest, ClusterResponse
from app.response_builder import build_response
from app.routes.read_request import read_body, read_cluster_request
from app.rules import ResponseRules

cluster_router: APIRouter = APIRouter()


@cluster_router.post(path="/")
@log_info(outputs=("status_code",))
@log_debug
def cluster_endpoint(*, request: Request, body: Annotated[bytes, Depends(dependency=read_body)]) -> Response:
    settings: Settings = request.app.state.settings
    rules: ResponseRules = request.app.state.rules
    cluster_request: ClusterRequest = read_cluster_request(
        headers=dict(request.headers), body=body, settings=settings
    )
    cluster_response: ClusterResponse | None = None
    try:
        cluster_response = send_to_cluster(request=cluster_request, settings=settings.forwarding)
        cluster_response = build_response(cluster_response=cluster_response, rules=rules)
    except RequestFailedError as failure:
        record_failure(
            request=cluster_request,
            failure=failure,
            cluster_response=cluster_response,
            redacted_fields=rules.redacted_fields,
            settings=settings,
        )
        cluster_response = failure_response(
            failure=failure, cluster_response=cluster_response, settings=settings
        )
    return Response(
        content=cluster_response.content,
        status_code=cluster_response.status_code,
        headers=cluster_response.headers,
    )
