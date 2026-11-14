from app.config.failures import FailureSettings
from app.logger.decorators import log_debug


@log_debug
def reason_parts(*, text: str, settings: FailureSettings) -> list[str]:
    length: int = settings.part_length
    parts: list[str] = [text[start : start + length] for start in range(0, len(text), length)]
    if len(parts) <= settings.max_parts:
        return parts
    kept: list[str] = parts[: settings.max_parts - 1]
    unsent: int = len(text) - length * len(kept)
    return [*kept, settings.unsent_characters_message.format(count=unsent)]


@log_debug
def shortened_field(*, field: str | None, settings: FailureSettings) -> str | None:
    if field is None or len(field) <= settings.part_length:
        return field
    prefix: str = settings.shortened_field_prefix
    return prefix + field[len(field) - settings.part_length + len(prefix) :]
