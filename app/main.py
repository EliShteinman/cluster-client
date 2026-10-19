from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.config import Settings
from app.ignored_fields import load_ignored_fields
from app.logger import configure_logging, log_debug, reset_logging
from app.logger.tracing import TraceMiddleware
from app.routes import cluster_router, health_router
from app.schema import load_schema


@log_debug
def create_app(*, settings: Settings) -> FastAPI:
    app: FastAPI = FastAPI(
        title=settings.application.title, version=settings.application.version, lifespan=lifespan
    )
    app.state.settings = settings
    app.add_middleware(TraceMiddleware, settings=settings.log.tracing)
    app.include_router(router=health_router)
    app.include_router(router=cluster_router)
    return app


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    settings: Settings = app.state.settings
    configure_logging(settings=settings.log)
    app.state.schema = load_schema(path=settings.validation.schema_path)
    app.state.ignored_fields = load_ignored_fields(path=settings.validation.ignored_fields_path)
    yield
    reset_logging()
