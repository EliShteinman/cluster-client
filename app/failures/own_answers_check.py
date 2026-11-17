import json
import sys

from pydantic import JsonValue

from app.config.settings import Settings
from app.errors import SchemaLoadError
from app.failures.answers import failure_codes
from app.failures.body import failure_body
from app.logger.decorators import log_debug, log_info
from app.models import ErrorBodyLimits, FailureBody, FailureDetails
from app.rules.response_rules import ResponseRules
from app.rules.schema import first_violation


@log_info()
@log_debug
def check_own_answers(*, rules: ResponseRules, settings: Settings) -> None:
    limits: ErrorBodyLimits = rules.error_limits
    if limits.max_parts < 1 or limits.part_length < 1:
        raise SchemaLoadError(
            path=settings.validation.schema_path,
            reason="the reason of an error body must hold at least one part of at least one character",
        )
    error_codes: list[str] = [code.error_code for code in failure_codes(settings=settings.failures)]
    rule_names: list[str] = [
        settings.failures.not_json_rule,
        settings.failures.too_deep_rule,
        *type(rules.schema_validator).VALIDATORS,
    ]
    sample: FailureBody = failure_body(
        details=sample_details(error_codes=error_codes, rule_names=rule_names, limits=limits),
        limits=limits,
        settings=settings.failures,
    )
    problems: list[str] = [
        *too_long(values=error_codes, limit=limits.error_length, name="error"),
        *too_long(values=rule_names, limit=limits.rule_length, name="rule"),
        *too_long(
            values=[settings.failures.unsent_characters_message.format(count=sys.maxsize)],
            limit=limits.part_length,
            name="reason part",
        ),
        *too_long(
            values=[settings.failures.shortened_field_prefix + "$"], limit=limits.field_length, name="field"
        ),
        *schema_problems(sample=sample, rules=rules),
    ]
    if problems:
        raise SchemaLoadError(path=settings.validation.schema_path, reason="; ".join(problems))


@log_debug
def too_long(*, values: list[str], limit: int, name: str) -> list[str]:
    return [f"{name} {value!r} is longer than {limit}" for value in values if len(value) > limit]


@log_debug
def sample_details(
    *, error_codes: list[str], rule_names: list[str], limits: ErrorBodyLimits
) -> FailureDetails:
    parts: int = limits.part_length * limits.max_parts
    return FailureDetails(
        error=max(error_codes, key=len),
        rule=max(rule_names, key=len),
        field="$." + "a" * limits.field_length,
        reason="x" * (parts + 1),
    )


@log_debug
def schema_problems(*, sample: FailureBody, rules: ResponseRules) -> list[str]:
    body: JsonValue = json.loads(s=sample.model_dump_json(exclude_none=True))
    violation: str | None = first_violation(body=body, schema=rules.schema_validator)
    return [] if violation is None else [f"an error body breaks the schema at {violation}"]
