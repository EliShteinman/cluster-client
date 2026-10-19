import json
import logging
import sys
import traceback
from datetime import UTC, datetime
from logging.handlers import RotatingFileHandler

from pydantic import JsonValue

from app.config import (
    TEXT_ENCODING,
    ConsoleSettings,
    FileSettings,
    FormattingSettings,
    LogFormat,
    LoggingSettings,
    LogLevel,
)
from app.logger.tracing import TRACE_FIELDS, TraceContextFilter

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


def console_handler(*, settings: ConsoleSettings, formatting: FormattingSettings) -> logging.Handler:
    return prepare_handler(
        handler=logging.StreamHandler(stream=sys.stdout),
        level=settings.level,
        log_format=settings.format,
        formatting=formatting,
    )


def file_handler(*, settings: FileSettings, formatting: FormattingSettings) -> logging.Handler:
    settings.path.parent.mkdir(parents=True, exist_ok=True)
    return prepare_handler(
        handler=RotatingFileHandler(
            filename=settings.path,
            maxBytes=settings.max_bytes,
            backupCount=settings.backup_count,
            encoding=TEXT_ENCODING,
        ),
        level=settings.level,
        log_format=settings.format,
        formatting=formatting,
    )


def prepare_handler(
    *, handler: logging.Handler, level: LogLevel, log_format: LogFormat, formatting: FormattingSettings
) -> logging.Handler:
    handler.setLevel(level=level)
    handler.setFormatter(fmt=build_formatter(log_format=log_format, settings=formatting))
    handler.addFilter(filter=TraceContextFilter())
    return handler


_installed: list[tuple[logging.Logger, logging.Handler]] = []


def configure_logging(*, settings: LoggingSettings) -> None:
    reset_logging()
    root: logging.Logger = logging.getLogger()
    root.setLevel(level=settings.level)
    if settings.console.enabled:
        install(
            logger=root, handler=console_handler(settings=settings.console, formatting=settings.formatting)
        )
    if settings.file.enabled:
        install(logger=root, handler=file_handler(settings=settings.file, formatting=settings.formatting))
    if settings.failure_file.enabled:
        install(
            logger=logging.getLogger(name=settings.failure_file.logger_name),
            handler=file_handler(settings=settings.failure_file, formatting=settings.formatting),
        )


def reset_logging() -> None:
    for logger, handler in _installed:
        logger.removeHandler(hdlr=handler)
        handler.close()
    _installed.clear()


def install(*, logger: logging.Logger, handler: logging.Handler) -> None:
    logger.addHandler(hdlr=handler)
    _installed.append((logger, handler))
