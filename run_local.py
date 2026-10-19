from pathlib import Path

from app.config import (
    ConsoleSettings,
    FailureFileSettings,
    FileSettings,
    LogFormat,
    LoggingSettings,
    ServerSettings,
    Settings,
)
from app.main import create_app
from app.server import serve

LOCAL_SETTINGS: Settings = Settings(
    _env_file=None,
    server=ServerSettings(host="127.0.0.1", port=8000),
    log=LoggingSettings(
        level="DEBUG",
        console=ConsoleSettings(level="DEBUG", format=LogFormat.LINE),
        file=FileSettings(enabled=True, format=LogFormat.JSON, path=Path("logs/local.log")),
        failure_file=FailureFileSettings(path=Path("logs/local-failures.log")),
    ),
)

if __name__ == "__main__":
    serve(app=create_app(settings=LOCAL_SETTINGS), settings=LOCAL_SETTINGS.server)
