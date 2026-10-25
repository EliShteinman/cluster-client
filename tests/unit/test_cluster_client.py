import pytest
import requests
from requests.structures import CaseInsensitiveDict
from urllib3.exceptions import MaxRetryError, ProtocolError

from app.cluster_client import outgoing_headers, returned_headers, send_to_cluster
from app.config import ForwardingSettings, TracingSettings
from app.errors import ClusterUnreachableError, ConnectionFailedError, NoResponseError
from app.logger.tracing import TraceContext, bind_trace_context, parse_traceparent
from app.models import ClusterRequest, ClusterResponse
from tests.support.fake_cluster_api import FakeClusterApi, SentRequest
from tests.support.requests import CLUSTER_REQUEST, CLUSTER_URL

FORWARDING: ForwardingSettings = ForwardingSettings()
TRACING: TracingSettings = TracingSettings()
TRACE: TraceContext = TraceContext(trace_id="4bf92f3577b34da6a3ce929d0e0e4736", span_id="00f067aa0ba902b7")
FULL_REQUEST: ClusterRequest = ClusterRequest(
    method="POST", url=CLUSTER_URL, authorization="Basic abc", content_type="application/json", body=b"{}"
)
CONNECT_FAILURE: MaxRetryError = MaxRetryError(pool=None, url="/", reason="refused")


def send(*, request: ClusterRequest) -> ClusterResponse:
    return send_to_cluster(request=request, settings=FORWARDING, tracing=TRACING)


def test_authorization_goes_under_the_configured_header() -> None:
    headers: dict[str, str] = outgoing_headers(
        request=CLUSTER_REQUEST, settings=ForwardingSettings(authorization_header="x-auth"), tracing=TRACING
    )

    assert headers["x-auth"] == "Basic abc"


def test_content_type_is_sent_only_when_given() -> None:
    assert "content-type" not in outgoing_headers(
        request=CLUSTER_REQUEST, settings=FORWARDING, tracing=TRACING
    )


def test_content_type_is_forwarded_when_given() -> None:
    headers: dict[str, str] = outgoing_headers(request=FULL_REQUEST, settings=FORWARDING, tracing=TRACING)

    assert headers["content-type"] == "application/json"


def test_no_traceparent_without_an_active_trace() -> None:
    assert "traceparent" not in outgoing_headers(
        request=CLUSTER_REQUEST, settings=FORWARDING, tracing=TRACING
    )


def test_traceparent_continues_the_active_trace() -> None:
    with bind_trace_context(context=TRACE):
        headers: dict[str, str] = outgoing_headers(
            request=CLUSTER_REQUEST, settings=FORWARDING, tracing=TRACING
        )

    sent: TraceContext | None = parse_traceparent(header=headers["traceparent"])
    assert sent is not None
    assert sent.trace_id == TRACE.trace_id


def test_passed_through_headers_are_sent() -> None:
    request: ClusterRequest = CLUSTER_REQUEST.model_copy(
        update={"passed_through_headers": {"x-task-id": "t1"}}
    )

    assert outgoing_headers(request=request, settings=FORWARDING, tracing=TRACING)["x-task-id"] == "t1"


def test_passed_through_header_cannot_replace_the_authorization() -> None:
    request: ClusterRequest = CLUSTER_REQUEST.model_copy(
        update={"passed_through_headers": {"authorization": "Basic other"}}
    )

    assert outgoing_headers(request=request, settings=FORWARDING, tracing=TRACING)["authorization"] == (
        "Basic abc"
    )


def test_recomputed_headers_are_not_returned() -> None:
    response: requests.Response = requests.Response()
    response.headers = CaseInsensitiveDict(data={"Content-Length": "2", "x-cluster": "1"})

    assert returned_headers(response=response, settings=FORWARDING) == {"x-cluster": "1"}


def test_request_reaches_the_cluster_as_built(fake_cluster: FakeClusterApi) -> None:
    send(request=FULL_REQUEST)

    sent: SentRequest = fake_cluster.requests[0]
    assert (sent.method, str(sent.url), sent.content) == ("POST", CLUSTER_URL, b"{}")


def test_cluster_answer_becomes_a_cluster_response(fake_cluster: FakeClusterApi) -> None:
    fake_cluster.respond_with_json(status_code=201, body={"uid": 7}, headers={"x-cluster": "1"})

    response: ClusterResponse = send(request=CLUSTER_REQUEST)

    assert (response.status_code, response.content, response.headers["x-cluster"]) == (201, b'{"uid":7}', "1")


def test_unreachable_cluster_raises(fake_cluster: FakeClusterApi) -> None:
    fake_cluster.go_offline()

    with pytest.raises(ClusterUnreachableError, match="cluster:9443"):
        send(request=CLUSTER_REQUEST)


@pytest.mark.parametrize(
    ("error", "raised"),
    [
        (requests.ConnectionError(CONNECT_FAILURE), ConnectionFailedError),
        (requests.ConnectTimeout(CONNECT_FAILURE), ConnectionFailedError),
        (requests.ConnectionError(ProtocolError("Connection aborted.")), NoResponseError),
        (requests.ReadTimeout("read timed out"), NoResponseError),
        (requests.exceptions.ChunkedEncodingError(ProtocolError("incomplete")), NoResponseError),
    ],
    ids=["refused", "connect timeout", "closed after send", "read timeout", "cut answer"],
)
def test_failure_says_whether_the_request_was_sent(
    fake_cluster: FakeClusterApi, error: requests.RequestException, raised: type[ClusterUnreachableError]
) -> None:
    fake_cluster.fail_with(error=error)

    with pytest.raises(raised):
        send(request=CLUSTER_REQUEST)
