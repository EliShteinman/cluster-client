from fastapi.security import HTTPBasic
from starlette.requests import Request

from app.config.failures import FailureCode
from app.config.settings import Settings
from app.logger.decorators import log_debug
from app.models import FailureBody, TargetRequest
from app.routes.read_request import own_headers

type OpenApiObject = dict[str, object]


class BasicAuthDocumentation(HTTPBasic):
    async def __call__(self, request: Request) -> None:  # pyright: ignore[reportIncompatibleMethodOverride]
        return None


@log_debug
def failure_responses(*, settings: Settings) -> dict[int | str, OpenApiObject]:
    codes: list[FailureCode] = [code for _, code in settings.failures if isinstance(code, FailureCode)]
    statuses: list[int] = sorted({code.status_code for code in codes})
    return {
        status: documented_failure(
            error_codes=[code.error_code for code in codes if code.status_code == status],
            with_target_status=status == settings.failures.rejected.status_code,
            settings=settings,
        )
        for status in statuses
    }


@log_debug
def documented_failure(
    *, error_codes: list[str], with_target_status: bool, settings: Settings
) -> OpenApiObject:
    headers: OpenApiObject = {
        settings.failures.error_header: {
            "description": "On every answer the cluster client writes itself; never on a target answer",
            "schema": {"type": "string", "enum": error_codes},
        }
    }
    if with_target_status:
        headers[settings.failures.target_status_header] = {
            "description": f"The target's status, on {settings.failures.rejected.error_code} only",
            "schema": {"type": "integer"},
        }
    return {"model": FailureBody, "description": ", ".join(error_codes), "headers": headers}


@log_debug
def request_documentation(*, settings: Settings) -> OpenApiObject:
    return {
        "description": forwarding_rule(settings=settings),
        "parameters": [
            *target_request_headers(settings=settings),
            *documented_target_headers(settings=settings),
        ],
        "requestBody": {
            "required": False,
            "description": "Sent to the target as is",
            "content": {"*/*": {"schema": {}}},
        },
    }


@log_debug
def forwarding_rule(*, settings: Settings) -> str:
    prefix: str = settings.headers.target_prefix
    refused: str = ", ".join(prefix + name for name in sorted(settings.headers.refused_target_headers))
    return (
        f"Every header that starts with {prefix} is sent to the target without the prefix "
        f"({prefix}authorization becomes authorization); no other header reaches the target. "
        f"{settings.headers.method} and {settings.headers.url} are read, never sent. "
        f"Refused with {settings.failures.invalid_request.error_code}: {refused}."
    )


@log_debug
def target_request_headers(*, settings: Settings) -> list[OpenApiObject]:
    field_schemas: OpenApiObject = TargetRequest.model_json_schema()["properties"]
    return [
        {
            "name": header,
            "in": "header",
            "required": TargetRequest.model_fields[field].is_required(),
            "schema": field_schemas[field],
        }
        for field, header in own_headers(settings=settings.headers).items()
    ]


@log_debug
def documented_target_headers(*, settings: Settings) -> list[OpenApiObject]:
    return [
        {
            "name": settings.headers.target_prefix + name,
            "in": "header",
            "required": False,
            "description": f"Sent to the target as {name}; left out, the target gets no {name}",
            "schema": {"type": "string"},
        }
        for name in settings.headers.documented_target_headers
    ]
