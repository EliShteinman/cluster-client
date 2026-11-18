import logging
from contextvars import ContextVar, Token

from starlette.types import ASGIApp, Receive, Scope, Send

quiet_request: ContextVar[bool] = ContextVar("quiet_request", default=False)


class QuietPathsMiddleware:
    def __init__(self, app: ASGIApp, *, paths: frozenset[str]) -> None:
        self.app: ASGIApp = app
        self.paths: frozenset[str] = paths

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http" or scope["path"] not in self.paths:
            await self.app(scope, receive, send)
            return
        token: Token[bool] = quiet_request.set(True)
        try:
            await self.app(scope, receive, send)
        finally:
            quiet_request.reset(token)


class QuietRequestFilter(logging.Filter):
    def __init__(self, *, kept_level: int) -> None:
        super().__init__()
        self.kept_level: int = kept_level

    def filter(self, record: logging.LogRecord) -> bool:
        return record.levelno >= self.kept_level or not quiet_request.get()
