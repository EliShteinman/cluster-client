import logging
import re
import secrets
from collections.abc import Iterator
from contextlib import contextmanager
from contextvars import ContextVar, Token

from starlette.datastructures import Headers, MutableHeaders
from starlette.types import ASGIApp, Message, Receive, Scope, Send

from app.config import FrozenModel, TracingSettings

TRACE_ID_BYTES: int = 16
SPAN_ID_BYTES: int = 8
TRACE_FIELDS: tuple[str, ...] = ("trace_id", "span_id")
SUPPORTED_VERSION: str = "00"
SAMPLED_FLAGS: str = "01"
TRACEPARENT_PATTERN: re.Pattern[str] = re.compile(
    pattern=r"^00-(?P<trace_id>(?!0{32})[0-9a-f]{32})-(?P<span_id>(?!0{16})[0-9a-f]{16})-[0-9a-f]{2}$"
)
HTTP_SCOPE: str = "http"
RESPONSE_START: str = "http.response.start"


class TraceContext(FrozenModel):
    trace_id: str
    span_id: str


_current_trace: ContextVar[TraceContext | None] = ContextVar("trace_context", default=None)


def new_trace_id() -> str:
    return secrets.token_hex(nbytes=TRACE_ID_BYTES)


def new_span_id() -> str:
    return secrets.token_hex(nbytes=SPAN_ID_BYTES)


def current_trace_context() -> TraceContext | None:
    return _current_trace.get()


@contextmanager
def bind_trace_context(*, context: TraceContext) -> Iterator[TraceContext]:
    token: Token[TraceContext | None] = _current_trace.set(context)
    try:
        yield context
    finally:
        _current_trace.reset(token)


def parse_traceparent(*, header: str | None) -> TraceContext | None:
    match: re.Match[str] | None = TRACEPARENT_PATTERN.match(string=(header or "").strip().lower())
    if match is None:
        return None
    return TraceContext(trace_id=match["trace_id"], span_id=match["span_id"])


def format_traceparent(*, context: TraceContext) -> str:
    return f"{SUPPORTED_VERSION}-{context.trace_id}-{context.span_id}-{SAMPLED_FLAGS}"


def trace_headers(*, header_name: str) -> dict[str, str]:
    context: TraceContext | None = current_trace_context()
    if context is None:
        return {}
    child: TraceContext = TraceContext(trace_id=context.trace_id, span_id=new_span_id())
    return {header_name: format_traceparent(context=child)}


class TraceContextFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        context: TraceContext | None = current_trace_context()
        if context is not None:
            record.trace_id = context.trace_id
            record.span_id = context.span_id
        return True


class TraceMiddleware:
    def __init__(self, app: ASGIApp, settings: TracingSettings) -> None:
        self._app: ASGIApp = app
        self._header: str = settings.traceparent_header

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != HTTP_SCOPE:
            await self._app(scope, receive, send)
            return
        context: TraceContext = self._context_of(headers=Headers(scope=scope))
        with bind_trace_context(context=context):
            await self._app(scope, receive, self._send_with_trace(send=send, context=context))

    def _context_of(self, *, headers: Headers) -> TraceContext:
        incoming: TraceContext | None = parse_traceparent(header=headers.get(key=self._header))
        trace_id: str = incoming.trace_id if incoming else new_trace_id()
        return TraceContext(trace_id=trace_id, span_id=new_span_id())

    def _send_with_trace(self, *, send: Send, context: TraceContext) -> Send:
        async def send_with_trace(message: Message) -> None:
            if message["type"] == RESPONSE_START:
                MutableHeaders(scope=message)[self._header] = format_traceparent(context=context)
            await send(message)

        return send_with_trace
