import logging

from app.config.logging import LoggingSettings
from app.logger.handlers import console_handler, file_handler

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
