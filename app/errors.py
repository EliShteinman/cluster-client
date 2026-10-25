from pathlib import Path


class ClusterClientError(Exception):
    pass


class SchemaLoadError(ClusterClientError):
    def __init__(self, *, path: Path, reason: str) -> None:
        super().__init__(f"cannot load the response schema from {path}: {reason}")


class FieldPathsLoadError(ClusterClientError):
    def __init__(self, *, path: Path, reason: str) -> None:
        super().__init__(f"cannot load the field paths from {path}: {reason}")


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
