from concurrent.futures import Future, ThreadPoolExecutor
from contextvars import copy_context

import requests
import urllib3
from urllib3.exceptions import InsecureRequestWarning, MaxRetryError

from app.config.forwarding import ForwardingSettings
from app.errors import (
    ConnectionFailedError,
    InvalidTargetRequestError,
    NoResponseError,
    RequestFailedError,
)
from app.logger.decorators import log_debug, log_info
from app.models import Answer, TargetRequest

urllib3.disable_warnings(category=InsecureRequestWarning)


@log_info(inputs=("request.method", "request.url"), outputs=("status_code",))
def send_to_target(*, request: TargetRequest, settings: ForwardingSettings) -> Answer:
    pool: ThreadPoolExecutor = ThreadPoolExecutor(max_workers=1)
    call: Future[requests.Response] = pool.submit(
        copy_context().run, call_target, request=request, settings=settings
    )
    try:
        response: requests.Response = call.result(timeout=settings.timeout_seconds)
    except TimeoutError as error:
        raise NoResponseError(
            url=request.url, reason=f"no full answer within {settings.timeout_seconds} seconds"
        ) from error
    except requests.RequestException as error:
        raise classified_error(url=request.url, error=error) from error
    finally:
        pool.shutdown(wait=False)
    return Answer(
        status_code=response.status_code,
        headers=returned_headers(response=response, settings=settings),
        content=response.content,
    )


def call_target(*, request: TargetRequest, settings: ForwardingSettings) -> requests.Response:
    return requests.request(
        method=request.method,
        url=request.url,
        headers=request.headers,
        data=request.body,
        timeout=(settings.connect_timeout_seconds, settings.timeout_seconds),
        allow_redirects=False,
        verify=False,  # noqa: S501 - the targets use internal certificates; the client does not verify them
    )


@log_debug
def classified_error(*, url: str, error: requests.RequestException) -> RequestFailedError:
    if isinstance(error, ValueError):
        return InvalidTargetRequestError(url=url, reason=str(error))
    if was_not_sent(error=error):
        return ConnectionFailedError(url=url, reason=str(error))
    return NoResponseError(url=url, reason=str(error))


@log_debug
def was_not_sent(*, error: requests.RequestException) -> bool:
    if isinstance(error, requests.exceptions.SSLError) or not isinstance(error, requests.ConnectionError):
        return False
    return any(isinstance(argument, MaxRetryError) for argument in error.args)


@log_debug
def returned_headers(*, response: requests.Response, settings: ForwardingSettings) -> dict[str, str]:
    return {
        name: value
        for name, value in response.headers.items()
        if name.lower() not in settings.recomputed_response_headers
        and not name.lower().startswith(settings.edge_header_prefix)
    }
