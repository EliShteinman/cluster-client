from pydantic import Field, SecretStr

from app.config.base import BaseConfig
from app.config.constants import BASIC_USERNAME_PATTERN
from app.config.field_types import LowercaseHeaderName


class AccessSettings(BaseConfig):
    header: LowercaseHeaderName = Field(default="authorization")
    scheme: str = Field(default="Basic", min_length=1)
    username: str = Field(pattern=BASIC_USERNAME_PATTERN)
    password: SecretStr = Field(min_length=1)
    challenge_header: LowercaseHeaderName = Field(default="www-authenticate")
    realm: str = Field(default="cluster-client", pattern=r'^[^"]+$')
