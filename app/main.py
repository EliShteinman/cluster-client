from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
from opentelemetry.sdk.trace import TracerProvider
from starlette.exceptions import HTTPException

from app.config.settings import Settings
from app.failures.handlers import internal_error_response, refused_request_response
from app.field_paths import load_field_paths
from app.logger.decorators import log_debug
from app.logger.setup import configure_logging, reset_logging
from app.routes.cluster_routes import cluster_router
from app.routes.health_routes import health_router
from app.schema import load_schema
from app.telemetry import start_telemetry


@log_debug
def create_app(*, settings: Settings) -> FastAPI:
    app: FastAPI = FastAPI(
        title=settings.application.title, version=settings.application.version, lifespan=lifespan
    )
    app.state.settings = settings
    FastAPIInstrumentor.instrument_app(app=app)
    app.exception_handler(exc_class_or_status_code=HTTPException)(refused_request_response)
    app.exception_handler(exc_class_or_status_code=Exception)(internal_error_response)
    app.include_router(router=health_router)
    app.include_router(router=cluster_router)
    return app


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None]:
    settings: Settings = app.state.settings
    configure_logging(settings=settings.log)
    tracer_provider: TracerProvider = start_telemetry(settings=settings.telemetry)
    app.state.schema = load_schema(path=settings.validation.schema_path)
    app.state.ignored_fields = load_field_paths(path=settings.validation.ignored_fields_path)
    app.state.redacted_fields = load_field_paths(path=settings.validation.redacted_fields_path)
    yield
    tracer_provider.shutdown()
    reset_logging()
