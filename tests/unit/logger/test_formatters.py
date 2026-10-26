import json
import logging
import sys

from pydantic import JsonValue

from app.config import FormattingSettings, LogFormat
from app.logger.formatters import build_formatter

FORMATTING: FormattingSettings = FormattingSettings()


def make_record(**extra: JsonValue) -> logging.LogRecord:
    return logging.makeLogRecord(dict={"name": "orders", "levelname": "INFO", "msg": "order 7", **extra})


def json_payload(*, record: logging.LogRecord) -> dict[str, JsonValue]:
    return json.loads(s=build_formatter(log_format=LogFormat.JSON, settings=FORMATTING).format(record))


def test_json_contains_the_message() -> None:
    assert json_payload(record=make_record())["message"] == "order 7"


def test_json_contains_level_and_logger() -> None:
    payload: dict[str, JsonValue] = json_payload(record=make_record())

    assert (payload["level"], payload["logger"]) == ("INFO", "orders")


def test_json_puts_user_fields_under_extra() -> None:
    assert json_payload(record=make_record(order_id=7))["extra"] == {"order_id": 7}


def test_json_contains_the_trace_id_when_present() -> None:
    assert json_payload(record=make_record(trace_id="abc"))["trace_id"] == "abc"


def test_json_contains_the_exception_traceback() -> None:
    try:
        raise ValueError("bad input")
    except ValueError:
        record: logging.LogRecord = make_record()
        record.exc_info = sys.exc_info()

    assert "ValueError: bad input" in json_payload(record=record)["exception"]


def test_line_shows_a_placeholder_without_a_trace() -> None:
    line: str = build_formatter(log_format=LogFormat.LINE, settings=FORMATTING).format(make_record())

    assert "trace_id=-" in line
