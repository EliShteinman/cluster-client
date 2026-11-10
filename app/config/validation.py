from pathlib import Path

from pydantic import Field

from app.config.base import BaseConfig


class ValidationSettings(BaseConfig):
    schema_path: Path = Field(default=Path("config/response-schema.json"))
    ignored_fields_path: Path = Field(default=Path("config/ignored-fields.json"))
    redacted_fields_path: Path = Field(default=Path("config/redacted-fields.json"))
