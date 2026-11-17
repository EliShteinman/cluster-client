import logging

from app.config.logging import FormattingSettings, LogFormat
from app.logger.formatters import build_formatter

LINE: logging.Formatter = build_formatter(log_format=LogFormat.LINE, settings=FormattingSettings())


def record_with_trace(trace_id: str | None) -> logging.LogRecord:
    fields: dict[str, object] = {"msg": "started"}
    if trace_id is not None:
        fields["otelTraceID"] = trace_id
    return logging.makeLogRecord(dict=fields)


def test_a_line_outside_a_trace_shows_the_placeholder() -> None:
    assert "trace_id=-" in LINE.format(record=record_with_trace(trace_id="0"))


def test_a_line_without_trace_fields_shows_the_placeholder() -> None:
    assert "trace_id=-" in LINE.format(record=record_with_trace(trace_id=None))


def test_a_line_inside_a_trace_shows_its_id() -> None:
    assert "trace_id=abc123" in LINE.format(record=record_with_trace(trace_id="abc123"))


def test_the_placeholder_does_not_change_the_shared_record() -> None:
    record: logging.LogRecord = record_with_trace(trace_id="0")
    LINE.format(record=record)
    assert vars(record)["otelTraceID"] == "0"
