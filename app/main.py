from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.config import Settings
from app.field_paths import load_field_paths
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
    app.state.ignored_fields = load_field_paths(path=settings.validation.ignored_fields_path)
    app.state.redacted_fields = load_field_paths(path=settings.log.failure_file.redacted_fields_path)
    yield
    reset_logging()
