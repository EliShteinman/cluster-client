import pytest

from app.logger.tracing import (
    TraceContext,
    bind_trace_context,
    current_trace_context,
    format_traceparent,
    parse_traceparent,
    trace_headers,
)

TRACE_ID: str = "4bf92f3577b34da6a3ce929d0e0e4736"
SPAN_ID: str = "00f067aa0ba902b7"
CONTEXT: TraceContext = TraceContext(trace_id=TRACE_ID, span_id=SPAN_ID)


def test_valid_traceparent_is_parsed() -> None:
    assert parse_traceparent(header=f"00-{TRACE_ID}-{SPAN_ID}-01") == CONTEXT


@pytest.mark.parametrize(
    "header",
    [
        None,
        "",
        "garbage",
        f"ff-{TRACE_ID}-{SPAN_ID}-01",
        f"00-{'0' * 32}-{SPAN_ID}-01",
        f"00-{TRACE_ID}-{'0' * 16}-01",
    ],
)
def test_invalid_traceparent_is_ignored(header: str | None) -> None:
    assert parse_traceparent(header=header) is None


def test_formatted_traceparent_parses_back() -> None:
    assert parse_traceparent(header=format_traceparent(context=CONTEXT)) == CONTEXT


def test_bound_context_is_current_inside_the_block() -> None:
    with bind_trace_context(context=CONTEXT):
        assert current_trace_context() == CONTEXT


def test_context_is_cleared_after_the_block() -> None:
    with bind_trace_context(context=CONTEXT):
        pass

    assert current_trace_context() is None


def test_outgoing_header_keeps_the_trace_id() -> None:
    with bind_trace_context(context=CONTEXT):
        header: str = trace_headers(header_name="traceparent")["traceparent"]

    assert header.split("-")[1] == TRACE_ID


def test_outgoing_header_opens_a_new_span() -> None:
    with bind_trace_context(context=CONTEXT):
        header: str = trace_headers(header_name="traceparent")["traceparent"]

    assert header.split("-")[2] != SPAN_ID


def test_no_outgoing_header_without_a_trace() -> None:
    assert trace_headers(header_name="traceparent") == {}
