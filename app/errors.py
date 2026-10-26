from pathlib import Path
from typing import ClassVar


class ClusterClientError(Exception):
    pass


class ConfigFileLoadError(ClusterClientError):
    content: ClassVar[str]

    def __init__(self, *, path: Path, reason: str) -> None:
        super().__init__(f"cannot load {self.content} from {path}: {reason}")


class SchemaLoadError(ConfigFileLoadError):
    content: ClassVar[str] = "the response schema"


class FieldPathsLoadError(ConfigFileLoadError):
    content: ClassVar[str] = "the field paths"


class RequestFailedError(ClusterClientError):
    def __init__(self, *, reason: str, field: str | None = None) -> None:
        super().__init__(reason)
        self.reason: str = reason
        self.field: str | None = field


class ClusterUnreachableError(RequestFailedError):
    def __init__(self, *, url: str, reason: str) -> None:
        super().__init__(reason=f"cannot reach {url}: {reason}")


class ConnectionFailedError(ClusterUnreachableError):
    pass


class NoResponseError(ClusterUnreachableError):
    pass


class ResponseRejectedError(RequestFailedError):
    pass
