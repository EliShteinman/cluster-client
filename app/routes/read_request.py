from fastapi import HTTPException, Request
from pydantic import ValidationError
from pydantic_core import ErrorDetails

from app.config.settings import Settings
from app.logger.decorators import log_debug
from app.models import ClusterRequest


@log_debug
async def read_body(*, request: Request) -> bytes:
    return await request.body()


@log_debug
def read_cluster_request(*, headers: dict[str, str], body: bytes, settings: Settings) -> ClusterRequest:
    header_of_field: dict[str, str] = settings.headers.model_dump()
    passed_through_headers: dict[str, str] = {
        name: value
        for name, value in headers.items()
        if name in settings.forwarding.passed_through_request_headers
    }
    try:
        return ClusterRequest.model_validate(
            obj={
                **{field: headers[name] for field, name in header_of_field.items() if name in headers},
                "passed_through_headers": passed_through_headers,
                "body": body,
            }
        )
    except ValidationError as error:
        raise HTTPException(
            status_code=settings.failures.invalid_request.status_code,
            detail=[
                named_by_header(error=detail, header_of_field=header_of_field)
                for detail in error.errors(include_url=False, include_input=False)
            ],
        ) from error


@log_debug
def named_by_header(*, error: ErrorDetails, header_of_field: dict[str, str]) -> ErrorDetails:
    return {**error, "loc": tuple(header_of_field.get(str(part), part) for part in error["loc"])}
