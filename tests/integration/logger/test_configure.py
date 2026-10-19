import logging
from pathlib import Path

from app.logger import configure_logging, reset_logging
from app.logger.tracing import TraceContext, bind_trace_context
from tests.support.logging_settings import JsonLines, json_file_settings, read_json_lines

FAILURE_LOGGER: str = "cluster_client.failures"


def test_records_are_written_as_json_lines(json_lines: JsonLines) -> None:
    logging.getLogger(name="orders").info(msg="persisted")

    assert json_lines()[-1]["message"] == "persisted"


def test_records_carry_the_active_trace(json_lines: JsonLines) -> None:
    with bind_trace_context(context=TraceContext(trace_id="a" * 32, span_id="b" * 16)):
        logging.getLogger(name="orders").info(msg="traced")

    assert json_lines()[-1]["trace_id"] == "a" * 32


def test_failures_go_to_the_failure_file(json_lines: JsonLines, failure_lines: JsonLines) -> None:
    logging.getLogger(name=FAILURE_LOGGER).warning(msg="rejected")

    assert failure_lines()[-1]["message"] == "rejected"


def test_failures_also_reach_the_main_file(json_lines: JsonLines) -> None:
    logging.getLogger(name=FAILURE_LOGGER).warning(msg="rejected")

    assert json_lines()[-1]["message"] == "rejected"


def test_other_records_stay_out_of_the_failure_file(json_lines: JsonLines, failure_lines: JsonLines) -> None:
    logging.getLogger(name="orders").warning(msg="not a failure")

    assert failure_lines() == []


def test_reconfigure_does_not_duplicate_handlers(log_path: Path, failure_log_path: Path) -> None:
    before: int = len(logging.getLogger().handlers)

    configure_logging(settings=json_file_settings(log_path=log_path, failure_log_path=failure_log_path))
    configure_logging(settings=json_file_settings(log_path=log_path, failure_log_path=failure_log_path))

    assert len(logging.getLogger().handlers) == before + 1


def test_reset_keeps_foreign_handlers(log_path: Path, failure_log_path: Path) -> None:
    foreign: logging.Handler = logging.NullHandler()
    logging.getLogger().addHandler(hdlr=foreign)
    configure_logging(settings=json_file_settings(log_path=log_path, failure_log_path=failure_log_path))

    reset_logging()

    assert foreign in logging.getLogger().handlers
    logging.getLogger().removeHandler(hdlr=foreign)


def test_reset_stops_writing(log_path: Path, failure_log_path: Path) -> None:
    configure_logging(settings=json_file_settings(log_path=log_path, failure_log_path=failure_log_path))
    reset_logging()

    logging.getLogger(name="orders").info(msg="after reset")

    assert read_json_lines(log_path=log_path) == []
