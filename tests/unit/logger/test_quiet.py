import asyncio
import logging
import re

import pytest
from starlette.types import Message, Receive, Scope, Send

from app.logger.quiet import QuietPathsMiddleware, QuietRequestFilter, quiet_request
from app.main import excluded_urls

QUIET_PATHS: frozenset[str] = frozenset({"/health/live", "/health/ready"})
RECORD: logging.LogRecord = logging.makeLogRecord(
    dict={"msg": "GET /health/live 200", "levelno": logging.INFO}
)
WARNING_RECORD: logging.LogRecord = logging.makeLogRecord(
    dict={"msg": "invalid_request: method not allowed", "levelno": logging.WARNING}
)
QUIET_FILTER: QuietRequestFilter = QuietRequestFilter(kept_level=logging.WARNING)


async def no_message() -> Message:
    return {"type": "http.request"}


async def ignore(message: Message) -> None:
    return None


def quiet_while_handling(*, path: str) -> bool:
    seen: list[bool] = []

    async def app(scope: Scope, receive: Receive, send: Send) -> None:
        seen.append(quiet_request.get())

    middleware: QuietPathsMiddleware = QuietPathsMiddleware(app, paths=QUIET_PATHS)
    asyncio.run(main=middleware({"type": "http", "path": path}, no_message, ignore))
    return seen[0]


def test_a_quiet_path_is_handled_quietly() -> None:
    assert quiet_while_handling(path="/health/live")


@pytest.mark.parametrize("path", ["/", "/health", "/health/live/x"])
def test_other_paths_are_not_quiet(path: str) -> None:
    assert not quiet_while_handling(path=path)


def test_records_of_a_quiet_request_are_dropped() -> None:
    token = quiet_request.set(True)
    try:
        assert not QUIET_FILTER.filter(RECORD)
    finally:
        quiet_request.reset(token)


def test_warnings_of_a_quiet_request_are_kept() -> None:
    token = quiet_request.set(True)
    try:
        assert QUIET_FILTER.filter(WARNING_RECORD)
    finally:
        quiet_request.reset(token)


def test_records_of_other_requests_are_kept() -> None:
    assert QUIET_FILTER.filter(RECORD)


@pytest.mark.parametrize(
    ("url", "excluded"),
    [
        ("http://pod:8000/health/live", True),
        ("http://pod:8000/health/ready", True),
        ("http://pod:8000/", False),
        ("http://pod:8000/health/live/x", False),
        ("http://pod:8000/anything/health/live", False),
        ("https://pod/health/ready", True),
    ],
)
def test_only_quiet_paths_are_left_out_of_tracing(url: str, excluded: bool) -> None:
    patterns: list[str] = excluded_urls(paths=QUIET_PATHS).split(",")

    assert any(re.search(pattern=pattern, string=url) for pattern in patterns) == excluded
