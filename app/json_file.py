import json
from pathlib import Path

from pydantic import JsonValue

from app.config.constants import TEXT_ENCODING
from app.errors import ConfigFileLoadError
from app.logger.decorators import log_debug


@log_debug
def read_json_file(*, path: Path, error: type[ConfigFileLoadError]) -> JsonValue:
    try:
        return json.loads(s=path.read_text(encoding=TEXT_ENCODING))
    except (OSError, json.JSONDecodeError) as reason:
        raise error(path=path, reason=str(reason)) from reason
