import asyncio
import logging

import pytest

from app.logger import log_debug


@log_debug
def add(*, left: int, right: int) -> int:
    return left + right


@log_debug
async def echo(*, value: int) -> int:
    return value


@log_debug
def fail(*, reason: str) -> None:
    raise ValueError(reason)


class Counter:
    @log_debug
    def increase(self, *, by: int) -> int:
        return by + 1


def messages_of(*, caplog: pytest.LogCaptureFixture) -> list[str]:
    return [record.getMessage() for record in caplog.records if record.name == __name__]


@pytest.fixture(autouse=True)
def debug_level(caplog: pytest.LogCaptureFixture) -> None:
    caplog.set_level(level=logging.DEBUG, logger=__name__)


def test_return_value_is_kept() -> None:
    assert add(left=2, right=3) == 5


def test_arguments_are_logged(caplog: pytest.LogCaptureFixture) -> None:
    add(left=2, right=3)

    assert messages_of(caplog=caplog)[0] == "add called with {'left': 2, 'right': 3}"


def test_result_is_logged(caplog: pytest.LogCaptureFixture) -> None:
    add(left=2, right=3)

    assert messages_of(caplog=caplog)[1].startswith("add returned 5 in ")


def test_self_is_not_logged(caplog: pytest.LogCaptureFixture) -> None:
    Counter().increase(by=1)

    assert messages_of(caplog=caplog)[0] == "Counter.increase called with {'by': 1}"


def test_async_result_is_logged(caplog: pytest.LogCaptureFixture) -> None:
    asyncio.run(echo(value=7))

    assert messages_of(caplog=caplog)[1].startswith("echo returned 7 in ")


def test_error_is_logged_and_raised_again(caplog: pytest.LogCaptureFixture) -> None:
    with pytest.raises(ValueError, match="boom"):
        fail(reason="boom")

    assert messages_of(caplog=caplog)[1].startswith("fail raised ValueError('boom') in ")


def test_records_are_debug(caplog: pytest.LogCaptureFixture) -> None:
    add(left=2, right=3)

    assert {record.levelno for record in caplog.records if record.name == __name__} == {logging.DEBUG}
