from fastapi import HTTPException, Request
from pydantic import ValidationError
from pydantic_core import ErrorDetails

from app.config.headers import HeaderSettings
from app.config.settings import Settings
from app.logger.decorators import log_debug
from app.models import TargetRequest


@log_debug
async def read_body(*, request: Request) -> bytes:
    return await request.body()


@log_debug
def read_target_request(*, headers: dict[str, str], body: bytes, settings: Settings) -> TargetRequest:
    header_of_field: dict[str, str] = own_headers(settings=settings.headers)
    target_headers: dict[str, str] = headers_for_target(headers=headers, settings=settings.headers)
    try:
        request: TargetRequest = TargetRequest.model_validate(
            obj={
                **{field: headers[name] for field, name in header_of_field.items() if name in headers},
                "headers": target_headers,
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
    refused: list[str] = refused_headers(target_headers=target_headers, settings=settings.headers)
    if refused:
        raise HTTPException(
            status_code=settings.failures.invalid_request.status_code,
            detail=settings.headers.refused_reason.format(headers=", ".join(refused)),
        )
    return request


@log_debug
def own_headers(*, settings: HeaderSettings) -> dict[str, str]:
    return {"method": settings.method, "url": settings.url}


@log_debug
def headers_for_target(*, headers: dict[str, str], settings: HeaderSettings) -> dict[str, str]:
    return {
        name.removeprefix(settings.target_prefix): value
        for name, value in headers.items()
        if name.startswith(settings.target_prefix)
    }


@log_debug
def refused_headers(*, target_headers: dict[str, str], settings: HeaderSettings) -> list[str]:
    return sorted(
        settings.target_prefix + name for name in target_headers if name in settings.refused_target_headers
    )


@log_debug
def named_by_header(*, error: ErrorDetails, header_of_field: dict[str, str]) -> ErrorDetails:
    return {**error, "loc": tuple(header_of_field.get(str(part), part) for part in error["loc"])}
