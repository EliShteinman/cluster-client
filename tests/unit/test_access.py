import pytest

from app.access import check_access
from app.errors import AccessDeniedError
from tests.support.access import ACCESS, ACCESS_HEADER_VALUE


def test_the_configured_credentials_are_let_in() -> None:
    check_access(header_value=ACCESS_HEADER_VALUE, settings=ACCESS)


@pytest.mark.parametrize(
    "header_value",
    [
        "",
        "Basic bWFuYWdlcjp3cm9uZw==",
        ACCESS_HEADER_VALUE.replace("Basic", "Bearer"),
        ACCESS_HEADER_VALUE.replace("Basic ", "Basic"),
    ],
    ids=["missing", "wrong password", "wrong scheme", "no space"],
)
def test_other_credentials_are_denied(header_value: str) -> None:
    with pytest.raises(AccessDeniedError):
        check_access(header_value=header_value, settings=ACCESS)


@pytest.mark.parametrize("scheme", ["basic", "BASIC", "bAsIc"])
def test_the_scheme_is_matched_in_any_case(scheme: str) -> None:
    check_access(header_value=ACCESS_HEADER_VALUE.replace("Basic", scheme), settings=ACCESS)
