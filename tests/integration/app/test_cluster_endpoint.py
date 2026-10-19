from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from httpx import Response

from app.config import Settings
from app.errors import SchemaLoadError
from app.logger.tracing import TraceContext, parse_traceparent
from app.main import create_app
from tests.support.app_settings import make_app_settings
from tests.support.fake_cluster_api import FakeClusterApi
from tests.support.logging_settings import JsonLines
from tests.support.requests import CLUSTER_HEADERS


def send(*, client: TestClient, headers: dict[str, str] = CLUSTER_HEADERS) -> Response:
    return client.post(url="/", headers=headers)


def trace_id_of(*, response: Response) -> str:
    context: TraceContext | None = parse_traceparent(header=response.headers["traceparent"])
    assert context is not None
    return context.trace_id


def test_valid_cluster_response_is_returned_unchanged(
    client: TestClient, fake_cluster: FakeClusterApi
) -> None:
    fake_cluster.respond_with_content(status_code=200, content=b'{"uid":1,  "name":"db"}')

    assert send(client=client).content == b'{"uid":1,  "name":"db"}'


def test_cluster_status_and_headers_are_returned(client: TestClient, fake_cluster: FakeClusterApi) -> None:
    fake_cluster.respond_with_json(status_code=201, body={"uid": 7}, headers={"x-cluster": "1"})

    response: Response = send(client=client)

    assert (response.status_code, response.headers["x-cluster"]) == (201, "1")


def test_empty_cluster_response_is_returned(client: TestClient, fake_cluster: FakeClusterApi) -> None:
    fake_cluster.respond_with_content(status_code=204, content=b"")

    assert send(client=client).status_code == 204


def test_schema_violation_is_rejected_with_the_failing_field(
    client: TestClient, fake_cluster: FakeClusterApi
) -> None:
    fake_cluster.respond_with_json(status_code=200, body={"uid": "one"})

    response: Response = send(client=client)

    assert (response.status_code, response.json()["field"]) == (502, "$.uid")


def test_unreachable_cluster_is_reported(client: TestClient, fake_cluster: FakeClusterApi) -> None:
    fake_cluster.go_offline()

    assert send(client=client).json()["error"] == "cluster_unreachable"


def test_rejection_is_written_to_the_failure_file(
    client: TestClient, fake_cluster: FakeClusterApi, failure_lines: JsonLines
) -> None:
    fake_cluster.respond_with_json(status_code=200, body={"uid": "one"})

    send(client=client)

    assert failure_lines()[-1]["extra"]["cluster_response"] == '{"uid":"one"}'


def test_failure_is_found_by_the_response_trace_id(
    client: TestClient, fake_cluster: FakeClusterApi, failure_lines: JsonLines
) -> None:
    fake_cluster.go_offline()

    response: Response = send(client=client)

    assert failure_lines()[-1]["trace_id"] == trace_id_of(response=response)


def test_success_writes_nothing_to_the_failure_file(client: TestClient, failure_lines: JsonLines) -> None:
    send(client=client)

    assert failure_lines() == []


def test_invalid_request_is_refused_before_the_cluster(
    client: TestClient, fake_cluster: FakeClusterApi
) -> None:
    response: Response = send(client=client, headers={"x-cluster-method": "GET"})

    assert (response.status_code, fake_cluster.requests) == (400, [])


def test_trace_reaches_the_cluster(client: TestClient, fake_cluster: FakeClusterApi) -> None:
    response: Response = send(client=client)

    sent: TraceContext | None = parse_traceparent(header=fake_cluster.requests[0].headers["traceparent"])
    assert sent is not None
    assert sent.trace_id == trace_id_of(response=response)


def test_missing_schema_stops_startup(log_path: Path, failure_log_path: Path, tmp_path: Path) -> None:
    settings: Settings = make_app_settings(
        log_path=log_path, failure_log_path=failure_log_path, schema_path=tmp_path / "missing.json"
    )

    with pytest.raises(SchemaLoadError), TestClient(app=create_app(settings=settings)):
        pass
