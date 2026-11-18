import pytest
from pydantic import ValidationError

from app.config.access import AccessSettings
from app.config.failures import FailureSettings
from app.config.headers import HeaderSettings
from app.config.settings import NoEnvFileSettings
from tests.support.access import ACCESS


@pytest.mark.parametrize(
    "headers",
    [HeaderSettings(method="x-target-method"), HeaderSettings(url="x-target-url")],
    ids=["method", "url"],
)
def test_an_own_request_header_with_the_target_prefix_stops_the_start(headers: HeaderSettings) -> None:
    with pytest.raises(ValidationError):
        NoEnvFileSettings(access=ACCESS, headers=headers)


def test_an_access_header_with_the_target_prefix_stops_the_start() -> None:
    access: AccessSettings = ACCESS.model_copy(update={"header": "x-target-authorization"})

    with pytest.raises(ValidationError):
        NoEnvFileSettings(access=access)


@pytest.mark.parametrize(
    "failures",
    [FailureSettings(error_header="x-gw-error"), FailureSettings(target_status_header="x-gw-status")],
    ids=["error header", "target status header"],
)
def test_an_own_answer_header_without_the_edge_prefix_stops_the_start(failures: FailureSettings) -> None:
    with pytest.raises(ValidationError):
        NoEnvFileSettings(access=ACCESS, failures=failures)


def test_own_answer_headers_match_the_edge_prefix_in_any_case() -> None:
    NoEnvFileSettings(access=ACCESS, failures=FailureSettings(error_header="X-Edge-Error"))
