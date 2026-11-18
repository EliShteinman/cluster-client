import json
from pathlib import Path

from pydantic import JsonValue

from app.config.constants import TEXT_ENCODING
from app.errors import ConfigFileLoadError, NonStandardJsonError
from app.logger.decorators import log_debug


@log_debug
def read_json_file(*, path: Path, error: type[ConfigFileLoadError]) -> JsonValue:
    try:
        return json.loads(s=path.read_text(encoding=TEXT_ENCODING))
    except (OSError, json.JSONDecodeError) as reason:
        raise error(path=path, reason=str(reason)) from reason


@log_debug
def read_json_body(*, content: bytes | str) -> JsonValue:
    return json.loads(s=content, parse_constant=refuse_constant)


@log_debug
def refuse_constant(constant: str) -> JsonValue:
    raise NonStandardJsonError(constant=constant)
