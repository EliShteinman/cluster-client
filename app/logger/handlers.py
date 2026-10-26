import logging
import sys
from logging.handlers import RotatingFileHandler

from app.config import TEXT_ENCODING, ConsoleSettings, FileSettings, FormattingSettings, HandlerSettings
from app.logger.formatters import build_formatter
from app.logger.tracing import TraceContextFilter


def console_handler(*, settings: ConsoleSettings, formatting: FormattingSettings) -> logging.Handler:
    return prepare_handler(
        handler=logging.StreamHandler(stream=sys.stdout), settings=settings, formatting=formatting
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
        settings=settings,
        formatting=formatting,
    )


def prepare_handler(
    *, handler: logging.Handler, settings: HandlerSettings, formatting: FormattingSettings
) -> logging.Handler:
    handler.setLevel(level=settings.level)
    handler.setFormatter(fmt=build_formatter(log_format=settings.format, settings=formatting))
    handler.addFilter(filter=TraceContextFilter())
    return handler
