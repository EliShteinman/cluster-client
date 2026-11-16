from app.config.failures import FailureSettings
from app.failures.reason_parts import reason_parts, shortened_field

SETTINGS: FailureSettings = FailureSettings()
LONG_REASON: str = "".join(str(number % 10) for number in range(1300))
TOO_LONG_REASON: str = "x" * (SETTINGS.part_length * 500 + 10)
LONG_FIELD: str = "$" + ".level" * 100 + ".authentication_admin_pass"


def test_every_reason_part_fits_the_firewall_length() -> None:
    assert (
        max(len(part) for part in reason_parts(text=LONG_REASON, settings=SETTINGS)) <= SETTINGS.part_length
    )


def test_reason_parts_join_back_to_the_whole_reason() -> None:
    assert "".join(reason_parts(text=LONG_REASON, settings=SETTINGS)) == LONG_REASON


def test_too_long_reason_is_cut_to_the_firewall_item_count() -> None:
    assert len(reason_parts(text=TOO_LONG_REASON, settings=SETTINGS)) == 500


def test_last_part_of_a_cut_reason_counts_the_unsent_characters() -> None:
    assert (
        reason_parts(text=TOO_LONG_REASON, settings=SETTINGS)[-1]
        == f"{SETTINGS.part_length + 10} more characters were not sent"
    )


def test_long_field_is_shortened_to_the_firewall_length() -> None:
    assert len(shortened_field(field=LONG_FIELD, settings=SETTINGS) or "") == SETTINGS.part_length


def test_shortened_field_keeps_the_end_of_the_path() -> None:
    assert (shortened_field(field=LONG_FIELD, settings=SETTINGS) or "").endswith(".authentication_admin_pass")


def test_shortened_field_starts_with_the_configured_prefix() -> None:
    assert (shortened_field(field=LONG_FIELD, settings=SETTINGS) or "").startswith("...")
