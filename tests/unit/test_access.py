import pytest

from app.access import check_access
from app.config.access import AccessSettings
from app.errors import AccessDeniedError
from tests.support.access import ACCESS, ACCESS_HEADER_VALUE


def test_the_configured_credentials_are_let_in() -> None:
    check_access(headers={"authorization": ACCESS_HEADER_VALUE}, settings=ACCESS)


@pytest.mark.parametrize(
    "headers",
    [
        {},
        {"authorization": ""},
        {"authorization": "Basic bWFuYWdlcjp3cm9uZw=="},
        {"authorization": ACCESS_HEADER_VALUE.replace("Basic", "Bearer")},
        {"authorization": ACCESS_HEADER_VALUE.replace("Basic ", "Basic")},
        {"x-cluster-authorization": ACCESS_HEADER_VALUE},
    ],
    ids=["missing", "empty", "wrong password", "wrong scheme", "no space", "other header"],
)
def test_other_credentials_are_denied(headers: dict[str, str]) -> None:
    with pytest.raises(AccessDeniedError):
        check_access(headers=headers, settings=ACCESS)


def test_the_header_name_comes_from_the_settings() -> None:
    settings: AccessSettings = ACCESS.model_copy(update={"header": "x-relay-key"})

    check_access(headers={"x-relay-key": ACCESS_HEADER_VALUE}, settings=settings)


@pytest.mark.parametrize("scheme", ["basic", "BASIC", "bAsIc"])
def test_the_scheme_is_matched_in_any_case(scheme: str) -> None:
    headers: dict[str, str] = {"authorization": ACCESS_HEADER_VALUE.replace("Basic", scheme)}

    check_access(headers=headers, settings=ACCESS)
