import base64
import secrets

from app.config.access import AccessSettings
from app.config.constants import TEXT_ENCODING
from app.errors import AccessDeniedError
from app.logger.decorators import log_debug


def check_access(*, header_value: str, settings: AccessSettings) -> None:
    scheme: str
    credentials: str
    scheme, _, credentials = header_value.partition(" ")
    same_scheme: bool = scheme.lower() == settings.scheme.lower()
    received: bytes = credentials.encode(encoding=TEXT_ENCODING)
    if not (same_scheme and secrets.compare_digest(received, expected_credentials(settings=settings))):
        raise AccessDeniedError(header=settings.header)


def expected_credentials(*, settings: AccessSettings) -> bytes:
    pair: bytes = f"{settings.username}:{settings.password.get_secret_value()}".encode(encoding=TEXT_ENCODING)
    return base64.b64encode(s=pair)


@log_debug
def login_challenge(*, settings: AccessSettings) -> str:
    return f'{settings.scheme} realm="{settings.realm}"'
