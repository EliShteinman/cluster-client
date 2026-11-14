from typing import cast

from pydantic import TypeAdapter

from app.config.failures import FailureCode
from app.config.settings import Settings
from app.logger.decorators import log_debug
from app.models import ClusterRequest, FailureBody

type OpenApiObject = dict[str, object]


@log_debug
def failure_responses(*, settings: Settings) -> dict[int | str, OpenApiObject]:
    codes: list[FailureCode] = [code for _, code in settings.failures if isinstance(code, FailureCode)]
    statuses: list[int] = sorted({code.status_code for code in codes})
    return {
        status: documented_failure(
            error_codes=[code.error_code for code in codes if code.status_code == status],
            with_cluster_status=status == settings.failures.rejected.status_code,
            settings=settings,
        )
        for status in statuses
    }


@log_debug
def documented_failure(
    *, error_codes: list[str], with_cluster_status: bool, settings: Settings
) -> OpenApiObject:
    headers: OpenApiObject = {
        settings.failures.error_header: {
            "description": "On every answer the cluster client writes itself; never on a cluster answer",
            "schema": {"type": "string", "enum": error_codes},
        }
    }
    if with_cluster_status:
        headers[settings.failures.cluster_status_header] = {
            "description": f"The cluster's status, on {settings.failures.rejected.error_code} only",
            "schema": {"type": "integer"},
        }
    return {"model": FailureBody, "description": ", ".join(error_codes), "headers": headers}


@log_debug
def request_documentation(*, settings: Settings) -> OpenApiObject:
    return {
        "parameters": [
            *cluster_request_headers(settings=settings),
            *passed_through_headers(settings=settings),
        ],
        "requestBody": {
            "required": False,
            "description": "Sent to the cluster as is",
            "content": {"*/*": {"schema": {}}},
        },
    }


@log_debug
def cluster_request_headers(*, settings: Settings) -> list[OpenApiObject]:
    header_of_field: dict[str, str] = settings.headers.model_dump()
    return [
        {
            "name": header,
            "in": "header",
            "required": ClusterRequest.model_fields[field].is_required(),
            "schema": field_schema(field=field),
        }
        for field, header in header_of_field.items()
    ]


@log_debug
def passed_through_headers(*, settings: Settings) -> list[OpenApiObject]:
    return [
        {
            "name": header,
            "in": "header",
            "required": False,
            "description": "Passed through to the cluster as is",
            "schema": {"type": "string"},
        }
        for header in sorted(settings.forwarding.passed_through_request_headers)
    ]


@log_debug
def field_schema(*, field: str) -> OpenApiObject:
    annotation: type[object] = cast(typ=type[object], val=ClusterRequest.model_fields[field].annotation)
    return TypeAdapter(type=annotation).json_schema()
