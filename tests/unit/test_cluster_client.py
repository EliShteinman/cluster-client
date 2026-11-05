import pytest
import requests
from requests.structures import CaseInsensitiveDict
from urllib3.exceptions import ProtocolError

from app.cluster_client import outgoing_headers, returned_headers, send_to_cluster
from app.config.forwarding import ForwardingSettings
from app.errors import ClusterUnreachableError, ConnectionFailedError, NoResponseError
from app.models import ClusterRequest, ClusterResponse
from tests.support.fake_cluster_api import CONNECT_FAILURE, FakeClusterApi, SentRequest
from tests.support.requests import CLUSTER_HEADERS, CLUSTER_REQUEST, CLUSTER_URL

FORWARDING: ForwardingSettings = ForwardingSettings()
FULL_REQUEST: ClusterRequest = ClusterRequest.model_validate(
    obj={
        **CLUSTER_HEADERS,
        "x-cluster-method": "POST",
        "content-type": "application/json",
        "body": b"{}",
    }
)


def send(*, request: ClusterRequest) -> ClusterResponse:
    return send_to_cluster(request=request, settings=FORWARDING)


def test_authorization_goes_under_the_configured_header() -> None:
    headers: dict[str, str] = outgoing_headers(
        request=CLUSTER_REQUEST, settings=ForwardingSettings(authorization_header="x-auth")
    )

    assert headers["x-auth"] == "Basic abc"


def test_passed_through_header_cannot_replace_the_authorization() -> None:
    request: ClusterRequest = CLUSTER_REQUEST.model_copy(
        update={"passed_through_headers": {"authorization": "Basic other"}}
    )

    assert outgoing_headers(request=request, settings=FORWARDING)["authorization"] == ("Basic abc")


def test_recomputed_headers_are_not_returned() -> None:
    response: requests.Response = requests.Response()
    response.headers = CaseInsensitiveDict(data={"Content-Length": "2", "x-cluster": "1"})

    assert returned_headers(response=response, settings=FORWARDING) == {"x-cluster": "1"}


def test_recomputed_header_is_configured_in_any_case() -> None:
    response: requests.Response = requests.Response()
    response.headers = CaseInsensitiveDict(data={"x-drop": "2", "x-cluster": "1"})
    settings: ForwardingSettings = ForwardingSettings(recomputed_response_headers=frozenset({"X-Drop"}))

    assert returned_headers(response=response, settings=settings) == {"x-cluster": "1"}


def test_redirects_are_left_to_the_manager(fake_cluster: FakeClusterApi) -> None:
    send(request=CLUSTER_REQUEST)

    assert fake_cluster.requests[0].allow_redirects is False


def test_request_reaches_the_cluster_as_built(fake_cluster: FakeClusterApi) -> None:
    send(request=FULL_REQUEST)

    sent: SentRequest = fake_cluster.requests[0]
    assert (sent.method, str(sent.url), sent.content) == ("POST", CLUSTER_URL, b"{}")


@pytest.mark.parametrize(
    ("error", "raised"),
    [
        (requests.ConnectionError(CONNECT_FAILURE), ConnectionFailedError),
        (requests.ConnectTimeout(CONNECT_FAILURE), ConnectionFailedError),
        (requests.exceptions.SSLError(CONNECT_FAILURE), NoResponseError),
        (requests.ConnectionError(ProtocolError("Connection aborted.")), NoResponseError),
        (requests.ReadTimeout("read timed out"), NoResponseError),
        (requests.exceptions.ChunkedEncodingError(ProtocolError("incomplete")), NoResponseError),
    ],
    ids=["refused", "connect timeout", "tls error", "closed after send", "read timeout", "cut answer"],
)
def test_failure_says_whether_the_request_was_sent(
    fake_cluster: FakeClusterApi, error: requests.RequestException, raised: type[ClusterUnreachableError]
) -> None:
    fake_cluster.fail_with(error=error)

    with pytest.raises(raised):
        send(request=CLUSTER_REQUEST)
