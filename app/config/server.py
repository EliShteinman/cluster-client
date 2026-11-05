from importlib.metadata import version

from pydantic import Field

from app.config.base import FrozenModel

DISTRIBUTION_NAME: str = "cluster-client"
MAX_PORT: int = 65535


class ServerSettings(FrozenModel):
    host: str = Field(default="127.0.0.1")
    port: int = Field(default=8000, ge=1, le=MAX_PORT)
    server_header: bool = Field(default=False)
    date_header: bool = Field(default=False)


class ApplicationSettings(FrozenModel):
    title: str = Field(default=DISTRIBUTION_NAME)
    version: str = Field(default_factory=lambda: version(distribution_name=DISTRIBUTION_NAME))
