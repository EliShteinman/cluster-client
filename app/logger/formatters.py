import json
import logging
import traceback
from datetime import UTC, datetime

from pydantic import JsonValue

from app.config import FormattingSettings, LogFormat
from app.logger.tracing import TRACE_FIELDS

MISSING_TRACE_PLACEHOLDER: str = "-"
STANDARD_RECORD_FIELDS: frozenset[str] = (
    frozenset(vars(logging.makeLogRecord(dict={}))) | {"message", "asctime"} | set(TRACE_FIELDS)
)


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        return json.dumps(obj=payload_of(record=record), ensure_ascii=False, default=str)


def payload_of(*, record: logging.LogRecord) -> dict[str, JsonValue]:
    payload: dict[str, JsonValue] = {
        "timestamp": datetime.fromtimestamp(record.created, tz=UTC).isoformat(timespec="milliseconds"),
        "level": record.levelname,
        "logger": record.name,
        "message": record.getMessage(),
    }
    payload |= {field: getattr(record, field) for field in TRACE_FIELDS if hasattr(record, field)}
    if extra := extra_fields_of(record=record):
        payload["extra"] = extra
    if record.exc_info:
        payload["exception"] = "".join(traceback.format_exception(*record.exc_info))
    return payload


def extra_fields_of(*, record: logging.LogRecord) -> dict[str, JsonValue]:
    return {name: value for name, value in vars(record).items() if name not in STANDARD_RECORD_FIELDS}


def build_formatter(*, log_format: LogFormat, settings: FormattingSettings) -> logging.Formatter:
    if log_format is LogFormat.JSON:
        return JsonFormatter()
    return logging.Formatter(
        fmt=settings.line_pattern,
        datefmt=settings.date_format,
        defaults=dict.fromkeys(TRACE_FIELDS, MISSING_TRACE_PLACEHOLDER),
    )
