from app.config import FailureCode, FailureSettings
from app.errors import ConnectionFailedError, NoResponseError, RequestFailedError
from app.logger import log_debug


@log_debug
def failure_code(*, failure: RequestFailedError, settings: FailureSettings) -> FailureCode:
    if isinstance(failure, ConnectionFailedError):
        return settings.connection_failed
    if isinstance(failure, NoResponseError):
        return settings.no_response
    return settings.rejected
