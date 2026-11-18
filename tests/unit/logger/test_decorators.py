import pytest

from app.logger.decorators import log_info


@log_info(inputs=("name",))
def greet(*, name: str) -> str:
    return f"hi {name}"


def info_message(caplog: pytest.LogCaptureFixture) -> str:
    return caplog.records[-1].getMessage()


def test_a_step_without_outputs_has_no_arrow(caplog: pytest.LogCaptureFixture) -> None:
    caplog.set_level(level="INFO")
    greet(name="eli")
    assert "->" not in info_message(caplog=caplog)


@log_info(inputs=("missing",), outputs=("no.such.path",))
def wrongly_logged(*, name: str) -> str:
    return name


def test_a_wrong_log_path_does_not_break_the_call() -> None:
    assert wrongly_logged(name="eli") == "eli"
