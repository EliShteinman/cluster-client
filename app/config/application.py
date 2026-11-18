from pydantic import Field

from app.config.base import BaseConfig
from app.config.constants import DISTRIBUTION_NAME


class ApplicationSettings(BaseConfig):
    title: str = Field(default=DISTRIBUTION_NAME)
