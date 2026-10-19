import uvicorn
from fastapi import FastAPI

from app.config import ServerSettings
from app.logger import log_debug


@log_debug
def serve(*, app: FastAPI, settings: ServerSettings) -> None:
    uvicorn.run(
        app=app,
        host=settings.host,
        port=settings.port,
        server_header=settings.server_header,
        date_header=settings.date_header,
        log_config=None,
    )
