from fastapi import HTTPException, Request
from pydantic import ValidationError

from app.config import Settings
from app.logger import log_debug
from app.models import ClusterRequest


@log_debug
async def read_body(*, request: Request) -> bytes:
    return await request.body()


@log_debug
def read_cluster_request(*, headers: dict[str, str], body: bytes, settings: Settings) -> ClusterRequest:
    try:
        return ClusterRequest.model_validate(obj={**headers, "body": body})
    except ValidationError as error:
        raise HTTPException(
            status_code=settings.failures.invalid_request_status_code,
            detail=error.errors(include_url=False, include_input=False),
        ) from error
