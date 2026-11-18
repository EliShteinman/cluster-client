from app.config.failures import FailureSettings
from app.logger.decorators import log_debug
from app.models import ErrorBodyLimits, FailureBody, FailureDetails


@log_debug
def failure_body(
    *, details: FailureDetails, limits: ErrorBodyLimits, settings: FailureSettings
) -> FailureBody:
    return FailureBody(
        error=details.error,
        rule=details.rule,
        field=shortened_field(field=details.field, limits=limits, settings=settings),
        reason=reason_parts(text=details.reason, limits=limits, settings=settings),
    )


@log_debug
def reason_parts(*, text: str, limits: ErrorBodyLimits, settings: FailureSettings) -> list[str]:
    length: int = limits.part_length
    parts: list[str] = [text[start : start + length] for start in range(0, len(text), length)]
    if len(parts) <= limits.max_parts:
        return parts
    kept: list[str] = parts[: limits.max_parts - 1]
    unsent: int = len(text) - length * len(kept)
    return [*kept, settings.unsent_characters_message.format(count=unsent)]


@log_debug
def shortened_field(*, field: str | None, limits: ErrorBodyLimits, settings: FailureSettings) -> str | None:
    if field is None or len(field) <= limits.field_length:
        return field
    prefix: str = settings.shortened_field_prefix
    return prefix + field[len(field) - limits.field_length + len(prefix) :]
