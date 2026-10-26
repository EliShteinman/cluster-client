import logging
import sys
from pathlib import Path

from app.config import ConsoleSettings, FileSettings, FormattingSettings
from app.logger.handlers import console_handler, file_handler
from app.logger.tracing import TraceContextFilter

FORMATTING: FormattingSettings = FormattingSettings()


def test_console_handler_writes_to_stdout() -> None:
    handler: logging.Handler = console_handler(settings=ConsoleSettings(), formatting=FORMATTING)

    assert handler.stream is sys.stdout


def test_console_level_comes_from_settings() -> None:
    handler: logging.Handler = console_handler(settings=ConsoleSettings(level="ERROR"), formatting=FORMATTING)

    assert handler.level == logging.ERROR


def test_file_handler_creates_its_directory(tmp_path: Path) -> None:
    log_path: Path = tmp_path / "nested" / "app.log"

    file_handler(settings=FileSettings(path=log_path), formatting=FORMATTING).close()

    assert log_path.parent.is_dir()


def test_every_handler_stamps_the_trace(tmp_path: Path) -> None:
    handler: logging.Handler = file_handler(
        settings=FileSettings(path=tmp_path / "app.log"), formatting=FORMATTING
    )
    handler.close()

    assert any(isinstance(record_filter, TraceContextFilter) for record_filter in handler.filters)
