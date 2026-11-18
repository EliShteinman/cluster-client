from opentelemetry.sdk.trace import TracerProvider
from starlette.datastructures import State

from app.config.settings import Settings
from app.logger.decorators import log_debug
from app.rules.response_rules import ResponseRules


@log_debug
def settings_of(*, state: State) -> Settings:
    settings: object = state.settings
    if not isinstance(settings, Settings):
        raise TypeError("the app state holds no Settings")
    return settings


@log_debug
def rules_of(*, state: State) -> ResponseRules:
    rules: object = state.rules
    if not isinstance(rules, ResponseRules):
        raise TypeError("the app state holds no ResponseRules")
    return rules


@log_debug
def tracer_provider_of(*, state: State) -> TracerProvider:
    tracer_provider: object = state.tracer_provider
    if not isinstance(tracer_provider, TracerProvider):
        raise TypeError("the app state holds no TracerProvider")
    return tracer_provider
