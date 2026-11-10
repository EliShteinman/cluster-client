from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from importlib.metadata import version

from fastapi import FastAPI
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
from opentelemetry.sdk.trace import TracerProvider
from starlette.exceptions import HTTPException

from app.config.constants import DISTRIBUTION_NAME
from app.config.settings import Settings
from app.failures.handlers import internal_error_response, refused_request_response
from app.logger.decorators import log_debug
from app.logger.setup import configure_logging, reset_logging
from app.routes.cluster_routes import cluster_router
from app.routes.health_routes import health_router
from app.rules import load_rules
from app.telemetry import build_tracer_provider, start_telemetry, stop_telemetry


@log_debug
def create_app(*, settings: Settings) -> FastAPI:
    app: FastAPI = FastAPI(
        title=settings.application.title,
        version=version(distribution_name=DISTRIBUTION_NAME),
        lifespan=lifespan,
    )
    tracer_provider: TracerProvider = build_tracer_provider(settings=settings.telemetry)
    app.state.settings = settings
    app.state.tracer_provider = tracer_provider
    FastAPIInstrumentor.instrument_app(app=app, tracer_provider=tracer_provider)
    app.exception_handler(exc_class_or_status_code=HTTPException)(refused_request_response)
    app.exception_handler(exc_class_or_status_code=Exception)(internal_error_response)
    app.include_router(router=health_router)
    app.include_router(router=cluster_router)
    return app


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None]:
    settings: Settings = app.state.settings
    tracer_provider: TracerProvider = app.state.tracer_provider
    configure_logging(settings=settings.log)
    start_telemetry(provider=tracer_provider)
    app.state.rules = load_rules(settings=settings.validation)
    yield
    stop_telemetry(provider=tracer_provider)
    reset_logging()
