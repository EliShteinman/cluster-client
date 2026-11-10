from pydantic import Field

from app.config.base import BaseConfig
from app.config.constants import DISTRIBUTION_NAME
from app.config.field_types import Port


class ServerSettings(BaseConfig):
    host: str = Field(default="127.0.0.1")
    port: Port = Field(default=8000)
    server_header: bool = Field(default=False)
    date_header: bool = Field(default=False)


class ApplicationSettings(BaseConfig):
    title: str = Field(default=DISTRIBUTION_NAME)
