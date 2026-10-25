import requests
import urllib3
from urllib3.exceptions import InsecureRequestWarning

from app.config import ForwardingSettings, TracingSettings
from app.errors import ClusterUnreachableError
from app.logger import log_debug, log_info
from app.logger.tracing import trace_headers
from app.models import ClusterRequest, ClusterResponse

urllib3.disable_warnings(category=InsecureRequestWarning)


@log_info(inputs=("request.method", "request.url"), outputs=("status_code",))
@log_debug
def send_to_cluster(
    *, request: ClusterRequest, settings: ForwardingSettings, tracing: TracingSettings
) -> ClusterResponse:
    try:
        response: requests.Response = requests.request(
            method=request.method,
            url=str(request.url),
            headers=outgoing_headers(request=request, settings=settings, tracing=tracing),
            data=request.body,
            timeout=settings.timeout_seconds,
            verify=False,  # noqa: S501 - the clusters use internal certificates; the client does not verify them
        )
    except (requests.ConnectionError, requests.Timeout) as error:
        raise ClusterUnreachableError(url=str(request.url), reason=str(error)) from error
    return ClusterResponse(
        status_code=response.status_code,
        headers=returned_headers(response=response, settings=settings),
        content=response.content,
    )


def outgoing_headers(
    *, request: ClusterRequest, settings: ForwardingSettings, tracing: TracingSettings
) -> dict[str, str]:
    headers: dict[str, str] = trace_headers(header_name=tracing.traceparent_header)
    headers[settings.authorization_header] = request.authorization.get_secret_value()
    if request.content_type is not None:
        headers[settings.content_type_header] = request.content_type
    return {**request.passed_through_headers, **headers}


@log_debug
def returned_headers(*, response: requests.Response, settings: ForwardingSettings) -> dict[str, str]:
    return {
        name: value
        for name, value in response.headers.items()
        if name.lower() not in settings.recomputed_response_headers
    }
