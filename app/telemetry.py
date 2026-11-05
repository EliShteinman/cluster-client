from opentelemetry import trace
from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
from opentelemetry.instrumentation.logging import LoggingInstrumentor  # pyright: ignore[reportMissingTypeStubs]
from opentelemetry.instrumentation.propagators import (
    TraceResponsePropagator,
    set_global_response_propagator,  # pyright: ignore[reportUnknownVariableType]
)
from opentelemetry.instrumentation.requests import RequestsInstrumentor
from opentelemetry.sdk.resources import SERVICE_NAME, Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor

from app.config.telemetry import TelemetrySettings
from app.logger.decorators import log_debug


@log_debug
def build_tracer_provider(*, settings: TelemetrySettings) -> TracerProvider:
    provider: TracerProvider = TracerProvider(
        resource=Resource.create(attributes={SERVICE_NAME: settings.service_name})
    )
    if settings.export_enabled:
        exporter: OTLPSpanExporter = OTLPSpanExporter(endpoint=settings.otlp_endpoint + settings.traces_path)
        provider.add_span_processor(span_processor=BatchSpanProcessor(span_exporter=exporter))
    return provider


@log_debug
def start_telemetry(*, settings: TelemetrySettings) -> TracerProvider:
    provider: TracerProvider = build_tracer_provider(settings=settings)
    trace.set_tracer_provider(tracer_provider=provider)
    LoggingInstrumentor().instrument(
        tracer_provider=provider, inject_trace_context=True, enable_log_auto_instrumentation=False
    )
    set_global_response_propagator(propagator=TraceResponsePropagator())
    RequestsInstrumentor().instrument(tracer_provider=provider)
    return provider
