from pydantic import Field

from app.config.base import BaseConfig
from app.config.field_types import LowercaseHeaderName


class HeaderSettings(BaseConfig):
    method: LowercaseHeaderName = Field(default="x-cluster-method")
    url: LowercaseHeaderName = Field(default="x-cluster-url")
    authorization: LowercaseHeaderName = Field(default="x-cluster-authorization")
    content_type: LowercaseHeaderName = Field(default="content-type")
