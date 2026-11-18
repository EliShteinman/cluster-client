import json
import logging
import traceback
from datetime import UTC, datetime

from pydantic import JsonValue

from app.config.logging import FormattingSettings, LogFormat

NO_TRACE: str = "0"
MISSING_TRACE_PLACEHOLDER: str = "-"
TRACE_FIELDS: dict[str, str] = {"trace_id": "otelTraceID", "span_id": "otelSpanID"}
STANDARD_RECORD_FIELDS: frozenset[str] = frozenset(vars(logging.makeLogRecord(dict={}))) | {
    "message",
    "asctime",
    "otelTraceID",
    "otelSpanID",
    "otelTraceSampled",
    "otelServiceName",
}


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        return json.dumps(obj=payload_of(record=record), ensure_ascii=False, default=str)


def payload_of(*, record: logging.LogRecord) -> dict[str, JsonValue]:
    payload: dict[str, JsonValue] = {
        "timestamp": datetime.fromtimestamp(timestamp=record.created, tz=UTC).isoformat(
            timespec="milliseconds"
        ),
        "level": record.levelname,
        "logger": record.name,
        "message": record.getMessage(),
    }
    payload |= trace_fields_of(record=record)
    if extra := extra_fields_of(record=record):
        payload["extra"] = extra
    if record.exc_info:
        payload["exception"] = "".join(traceback.format_exception(*record.exc_info))
    return payload


def trace_fields_of(*, record: logging.LogRecord) -> dict[str, JsonValue]:
    fields: dict[str, str] = {
        name: getattr(record, source, NO_TRACE) for name, source in TRACE_FIELDS.items()
    }
    return {name: value for name, value in fields.items() if value != NO_TRACE}


def extra_fields_of(*, record: logging.LogRecord) -> dict[str, JsonValue]:
    return {name: value for name, value in vars(record).items() if name not in STANDARD_RECORD_FIELDS}


class LineFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        return super().format(record=with_trace_placeholders(record=record))


def with_trace_placeholders(*, record: logging.LogRecord) -> logging.LogRecord:
    shown: logging.LogRecord = logging.makeLogRecord(dict=vars(record))
    for source in TRACE_FIELDS.values():
        if getattr(shown, source, NO_TRACE) == NO_TRACE:
            setattr(shown, source, MISSING_TRACE_PLACEHOLDER)
    return shown


def build_formatter(*, log_format: LogFormat, settings: FormattingSettings) -> logging.Formatter:
    if log_format is LogFormat.JSON:
        return JsonFormatter()
    return LineFormatter(fmt=settings.line_pattern, datefmt=settings.date_format)
