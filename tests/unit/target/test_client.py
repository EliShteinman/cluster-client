import pytest
import requests
from requests.structures import CaseInsensitiveDict
from urllib3.exceptions import ProtocolError

from app.config.forwarding import ForwardingSettings
from app.errors import (
    ConnectionFailedError,
    InvalidTargetRequestError,
    NoResponseError,
    RequestFailedError,
)
from app.models import Answer, TargetRequest
from app.target.client import returned_headers, send_to_target
from tests.support.fake_target_api import CONNECT_FAILURE, FakeTargetApi, SentRequest
from tests.support.requests import TARGET_REQUEST, TARGET_URL

FORWARDING: ForwardingSettings = ForwardingSettings()
FULL_REQUEST: TargetRequest = TARGET_REQUEST.model_copy(
    update={"method": "POST", "headers": {"content-type": "application/json"}, "body": b"{}"}
)


def send(*, request: TargetRequest) -> Answer:
    return send_to_target(request=request, settings=FORWARDING)


def test_recomputed_headers_are_not_returned() -> None:
    response: requests.Response = requests.Response()
    response.headers = CaseInsensitiveDict(data={"Content-Length": "2", "x-answer": "1"})

    assert returned_headers(response=response, settings=FORWARDING) == {"x-answer": "1"}


def test_recomputed_header_is_configured_in_any_case() -> None:
    response: requests.Response = requests.Response()
    response.headers = CaseInsensitiveDict(data={"x-drop": "2", "x-answer": "1"})
    settings: ForwardingSettings = ForwardingSettings(recomputed_response_headers=frozenset({"X-Drop"}))

    assert returned_headers(response=response, settings=settings) == {"x-answer": "1"}


def test_edge_headers_of_the_target_are_not_returned() -> None:
    response: requests.Response = requests.Response()
    response.headers = CaseInsensitiveDict(data={"X-Edge-Error": "timeout", "x-answer": "1"})

    assert returned_headers(response=response, settings=FORWARDING) == {"x-answer": "1"}


def test_redirects_are_left_to_the_manager(fake_target: FakeTargetApi) -> None:
    send(request=TARGET_REQUEST)

    assert fake_target.requests[0].allow_redirects is False


def test_request_reaches_the_target_as_built(fake_target: FakeTargetApi) -> None:
    send(request=FULL_REQUEST)

    sent: SentRequest = fake_target.requests[0]
    assert (sent.method, sent.url, sent.headers, sent.content) == (
        "POST",
        TARGET_URL,
        {"content-type": "application/json"},
        b"{}",
    )


@pytest.mark.parametrize(
    ("error", "raised"),
    [
        (requests.ConnectionError(CONNECT_FAILURE), ConnectionFailedError),
        (requests.ConnectTimeout(CONNECT_FAILURE), ConnectionFailedError),
        (requests.exceptions.SSLError(CONNECT_FAILURE), NoResponseError),
        (requests.ConnectionError(ProtocolError("Connection aborted.")), NoResponseError),
        (requests.ReadTimeout("read timed out"), NoResponseError),
        (requests.exceptions.ChunkedEncodingError(ProtocolError("incomplete")), NoResponseError),
        (requests.exceptions.InvalidURL("bad url"), InvalidTargetRequestError),
        (requests.exceptions.InvalidHeader("bad header"), InvalidTargetRequestError),
        (requests.exceptions.MissingSchema("no scheme"), InvalidTargetRequestError),
    ],
    ids=[
        "refused",
        "connect timeout",
        "tls error",
        "closed after send",
        "read timeout",
        "cut answer",
        "invalid url",
        "invalid header",
        "missing scheme",
    ],
)
def test_failure_says_whether_the_request_was_sent(
    fake_target: FakeTargetApi, error: requests.RequestException, raised: type[RequestFailedError]
) -> None:
    fake_target.fail_with(error=error)

    with pytest.raises(raised):
        send(request=TARGET_REQUEST)


def test_an_answer_slower_than_the_total_timeout_is_a_timeout(fake_target: FakeTargetApi) -> None:
    fake_target.answer_after(seconds=0.3)

    with pytest.raises(NoResponseError):
        send_to_target(
            request=TARGET_REQUEST,
            settings=ForwardingSettings(connect_timeout_seconds=0.01, timeout_seconds=0.05),
        )
