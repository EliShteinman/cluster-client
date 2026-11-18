import pytest
from starlette.datastructures import State

from app.config.settings import NoEnvFileSettings, Settings
from app.state import rules_of, settings_of
from tests.support.access import ACCESS
from tests.support.rules import RULES

SETTINGS: Settings = NoEnvFileSettings(access=ACCESS)


def test_the_loaded_settings_are_read_typed() -> None:
    assert settings_of(state=State(state={"settings": SETTINGS})) is SETTINGS


def test_the_loaded_rules_are_read_typed() -> None:
    assert rules_of(state=State(state={"rules": RULES})) is RULES


def test_a_state_without_settings_is_refused() -> None:
    with pytest.raises(TypeError):
        settings_of(state=State(state={"settings": None}))
