import json
import re
from pathlib import Path

import yaml
from pydantic import BaseModel, JsonValue

from app.config.base import ENV_NESTED_DELIMITER, ENV_PREFIX, TEXT_ENCODING
from app.config.headers import HEADERS_ENV_PREFIX, HeaderSettings
from app.config.settings import Settings

PROJECT_ROOT: Path = Path(__file__).parents[2]
VALUES_PATH: Path = PROJECT_ROOT / "helm" / "values.yaml"
VALUES_SCHEMA_PATH: Path = PROJECT_ROOT / "helm" / "values.schema.json"
DOCKERFILE_PATH: Path = PROJECT_ROOT / "docker" / "Dockerfile"
DOCKERFILE_ENV_PATTERN: re.Pattern[str] = re.compile(pattern=rf"({ENV_PREFIX}\w+)=(\S+)")
NOT_SET_BY_HELM: frozenset[str] = frozenset(
    {f"{ENV_PREFIX}SERVER__HOST", f"{ENV_PREFIX}SERVER__PORT", f"{ENV_PREFIX}APPLICATION__VERSION"}
)


def chart_values() -> dict[str, JsonValue]:
    return yaml.safe_load(stream=VALUES_PATH.read_text(encoding=TEXT_ENCODING))


def values_schema() -> dict[str, JsonValue]:
    return json.loads(s=VALUES_SCHEMA_PATH.read_text(encoding=TEXT_ENCODING))


def dockerfile_env() -> dict[str, str]:
    return dict(DOCKERFILE_ENV_PATTERN.findall(string=DOCKERFILE_PATH.read_text(encoding=TEXT_ENCODING)))


def env_names(*, model: type[BaseModel], prefix: str) -> set[str]:
    names: set[str] = set()
    for field_name, field in model.model_fields.items():
        name: str = f"{prefix}{field_name.upper()}"
        if isinstance(field.annotation, type) and issubclass(field.annotation, BaseModel):
            names |= env_names(model=field.annotation, prefix=f"{name}{ENV_NESTED_DELIMITER}")
        else:
            names.add(name)
    return names


def settings_env_names() -> set[str]:
    return env_names(model=Settings, prefix=ENV_PREFIX) | env_names(
        model=HeaderSettings, prefix=HEADERS_ENV_PREFIX
    )
