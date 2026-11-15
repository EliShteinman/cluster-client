from pydantic import SecretStr

from app.config.access import AccessSettings

ACCESS: AccessSettings = AccessSettings(username="manager", password=SecretStr(secret_value="s3cret:pass"))
ACCESS_HEADER_VALUE: str = "Basic bWFuYWdlcjpzM2NyZXQ6cGFzcw=="
