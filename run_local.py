from pathlib import Path

from pydantic import SecretStr

from app.config.access import AccessSettings
from app.config.logging import LoggingSettings
from app.config.server import ServerSettings
from app.config.settings import NoEnvFileSettings, Settings
from app.main import create_app
from app.server import serve

DEFAULT_LOGGING: LoggingSettings = LoggingSettings()
LOCAL_SETTINGS: Settings = NoEnvFileSettings(
    access=AccessSettings(username="manager", password=SecretStr(secret_value="local-password")),
    server=ServerSettings(host="0.0.0.0", port=8000),
    log=LoggingSettings(
        level="DEBUG",
        console=DEFAULT_LOGGING.console.model_copy(update={"level": "DEBUG"}),
        file=DEFAULT_LOGGING.file.model_copy(update={"enabled": True, "path": Path("logs/local.log")}),
        failure_file=DEFAULT_LOGGING.failure_file.model_copy(
            update={"path": Path("logs/local-failures.log")}
        ),
    ),
)

if __name__ == "__main__":
    serve(app=create_app(settings=LOCAL_SETTINGS), settings=LOCAL_SETTINGS.server)
