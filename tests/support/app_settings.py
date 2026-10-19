from pathlib import Path
from typing import Any

from app.config import ApplicationSettings, Settings, ValidationSettings
from tests.support.logging_settings import json_file_settings

TEST_APPLICATION: ApplicationSettings = ApplicationSettings(title="client-under-test", version="0.0.0-test")


def make_app_settings(
    *, log_path: Path, failure_log_path: Path, schema_path: Path, **overrides: Any
) -> Settings:
    return Settings(
        _env_file=None,
        log=json_file_settings(log_path=log_path, failure_log_path=failure_log_path),
        application=TEST_APPLICATION,
        validation=ValidationSettings(schema_path=schema_path),
        **overrides,
    )
