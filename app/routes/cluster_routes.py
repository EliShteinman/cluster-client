from typing import Annotated

from fastapi import Depends, Request, Response
from jsonschema import Draft202012Validator

from app.cluster_client import send_to_cluster
from app.config import Settings
from app.errors import RequestFailedError
from app.failures import failure_response, record_failure
from app.field_paths import FieldPath
from app.logger import log_debug, log_info
from app.models import ClusterRequest, ClusterResponse
from app.response_builder import build_response
from app.routes import cluster_router
from app.routes.read_request import read_body, read_cluster_request


@cluster_router.post(path="/")
@log_info(outputs=("status_code",))
@log_debug
def cluster_endpoint(*, request: Request, body: Annotated[bytes, Depends(dependency=read_body)]) -> Response:
    settings: Settings = request.app.state.settings
    schema: Draft202012Validator = request.app.state.schema
    ignored_fields: tuple[FieldPath, ...] = request.app.state.ignored_fields
    cluster_request: ClusterRequest = read_cluster_request(
        headers=dict(request.headers), body=body, settings=settings
    )
    cluster_response: ClusterResponse | None = None
    try:
        cluster_response = send_to_cluster(
            request=cluster_request, settings=settings.forwarding, tracing=settings.log.tracing
        )
        cluster_response = build_response(
            cluster_response=cluster_response, schema=schema, ignored_fields=ignored_fields
        )
    except RequestFailedError as failure:
        record_failure(
            request=cluster_request, failure=failure, cluster_response=cluster_response, settings=settings
        )
        cluster_response = failure_response(failure=failure, settings=settings)
    return Response(
        content=cluster_response.content,
        status_code=cluster_response.status_code,
        headers=cluster_response.headers,
    )
