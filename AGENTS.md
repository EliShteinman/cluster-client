# AGENTS.md — how this code works and how to change it

Read this whole file before you touch anything. It replaces the conversation history you do not have. The pages in
`docs/` describe the service for its users; this file is for changing the code.

## What the service is

`cluster-client` runs inside every firewalled network. A **manager** (redis-enterprise-services, in another network)
sends it one HTTP request. cluster-client sends that request to the **target** named in it (today the Redis
Enterprise REST API of a cluster; tomorrow MongoDB, a metrics endpoint, any HTTP API) and returns the answer.

It is a simple pipe, simple on purpose, and technology-neutral:

- The manager owns all business logic. cluster-client never fixes or interprets an answer.
- The only intervention is so the answer passes the firewall (DataPower). Three files in `helm/files/` decide it:
  `response-schema.json` (the firewall's own schema), `ignored-fields.json` (removed first), `redacted-fields.json`
  (left out of explanations and of the failure file). Another technology changes only these files.
- Otherwise the target's answer (status, headers, body) is returned **unchanged, byte for byte**.
- What the firewall would block, cluster-client rejects itself, with an error body that itself passes the firewall.
- Every failure says whether the call surely did not reach the target, or may have been done.
- FastAPI `/docs` is the owner's live contract. It is built from the settings; keep it complete.

The chain: manager → NGINX (adds `authorization`) → DataPower (authenticates, checks every answer body against the
schema) → cluster-client → target. Diagrams: `docs/diagrams/` (PNG next to every `.drawio`), index in
`docs/README.md`.

## The request flow (the whole program)

`POST /` → `target_endpoint` (`app/routes/target_routes.py:62`) is the orchestrator. Read it first; every step is one
visible call. Diagram: `docs/diagrams/flow.drawio.png`; every failure: `docs/failures.md`.

1. **Trace.** `FastAPIInstrumentor` (set up in `create_app`, `app/main.py:31`) continues the manager's `traceparent`
   or starts a trace. Requests to `log.quiet_paths` get no span (`excluded_urls`, `app/main.py:53`).
2. **Access.** `require_access` (`target_routes.py:55`), a route dependency, runs before the body is read. It passes
   only the value of `settings.access.header` (`authorization`) to `check_access` (`app/access.py:10`): scheme
   compared in any case, credentials compared in constant time with `expected_credentials` (`access.py:20`).
   Wrong → `AccessDeniedError` → `access_denied_response` → **401** `unauthorized` + `www-authenticate`
   (`login_challenge`, `access.py:26`). Nothing is sent.
3. **Body.** `read_body` (`app/routes/read_request.py:12`, async) reads the raw bytes.
4. **Request.** `read_target_request` (`read_request.py:17`) builds a `TargetRequest` (`app/models.py:21`): `method`
   from `x-edge-method`, `url` from `x-edge-url` (names from `header_of_field`, `read_request.py:53`), every header
   that starts with `headers.target_prefix` (`x-target-`) without the prefix, and the body. A validation error →
   `HTTPException` whose `loc` names the header (`named_by_header`, `read_request.py:58`). A header that is exactly
   `x-target-`, or one in `headers.refused_target_headers` → `HTTPException` with `headers.refused_reason`. Both →
   `refused_request_response` → **400** `invalid_request`. Nothing is sent.
5. **Send.** `send_to_target` (`app/target/client.py:22`) runs `call_target` (`:44`, `requests.request` with
   `timeout=(connect_timeout_seconds, timeout_seconds)`, `allow_redirects=False`, `verify=False`) in a
   one-thread pool inside `copy_context()`, and waits at most `forwarding.timeout_seconds` (28) for the whole call.
   - waiting too long → `NoResponseError` (**504** `timeout`, maybe done);
   - a `requests` error → `classified_error` (`:57`): a `ValueError` (refused before sending) →
     `InvalidTargetRequestError` (**400** `invalid_request`); `was_not_sent` (`:66`: a non-SSL `ConnectionError`
     wrapping `MaxRetryError`: refused, DNS, connect timeout) → `ConnectionFailedError` (**502**
     `connection_failed`); anything else (read timeout, connection cut, any TLS error) → `NoResponseError` (**504**).
   - the answer → `Answer` with the target's status, `returned_headers` (`:73`: without
     `forwarding.recomputed_response_headers` and without any `x-edge-*` header) and content.
6. **Check.** `build_response` (`app/target/response_builder.py:17`):
   - empty body (e.g. 204) → returned as is, unchecked;
   - `read_json_body` (`app/rules/json_reading.py:20`): not JSON, or `NaN`/`Infinity` (`refuse_constant`) →
     `ResponseRejectedError`, rule `failures.not_json_rule`, field `$`;
   - `remove_fields` (`app/rules/field_paths.py:44`) removes the ignored fields; it copies only along the removed paths
     and returns the same object when nothing was removed;
   - `validate_body` (`app/rules/schema.py:32`): `best_match` of the schema's errors; a violation → `ResponseRejectedError`
     with `rule` = the keyword and `field` = its `json_path`, and `reason` from `violation_at` (`:54`) on a copy without
     the redacted fields, else `failures.redacted_reason`. The original message is logged at DEBUG (`:42`);
   - a body too deep for Python (`RecursionError`) at either step → `too_deep` (`app/target/response_builder.py:46`), rule `too_deep`;
   - nothing removed → the **original** `Answer` object; else the body is re-encoded (`json.dumps`,
     `ensure_ascii=False`).
   All these are **502** `response_rejected`.
7. **Failure answer.** On any `RequestFailedError` from steps 5–6: `failed_request_answer`
   (`app/failures/answers.py:19`) picks the `FailureCode` (`failure_code`, `:52`), builds the `FailureRecord` once
   (`failure_record`, `:68`, with `redacted_content`, `:91`: the target's body without the redacted fields; a body
   that is not JSON is kept as it is), and calls `logged_answer` (`:102`). `logged_answer` writes the whole record
   at WARNING to the logger `log.failure_file.logger_name` and builds the answer: `content-type`, `x-edge-error`,
   `x-edge-target-status` when the target answered, and the body from `failure_body` (`app/failures/body.py:7`),
   cut to `rules.error_limits`.
8. **Own answers.** Everything else the service answers itself goes through the exception handlers of
   `app/failures/exception_handlers.py` and `own_failure_answer` (`:65`) to the same `logged_answer`:
   `HTTPException` (bad header, wrong path 404, wrong method 405) → `refused_request_response` (`:25`, keeps the
   exception's status and headers, e.g. `allow`), `invalid_request`, WARNING; `AccessDeniedError` →
   `access_denied_response` (`:41`), WARNING; any other exception → `internal_error_response` (`:53`), **500**
   `internal_error`, the error and its traceback, ERROR.
9. **Return.** `Response(content, status_code, headers)`; OpenTelemetry adds `traceresponse`.

## Startup

Diagram: `docs/diagrams/startup.drawio.png`.

1. `docker/entrypoint.py` builds `Settings()` from env and `.env`; `run_local.py` builds `NoEnvFileSettings` in code.
   Pydantic validation stops a bad value (see "Config" below and `Settings.own_headers_keep_their_prefixes`,
   `app/config/settings.py:42`).
2. `create_app(settings)` (`app/main.py:31`): a `TracerProvider` of its own (`build_tracer_provider`,
   `app/telemetry.py:19`, never global), `FastAPIInstrumentor`, `QuietPathsMiddleware`, three exception handlers,
   `health_router`, `build_target_router` (`target_routes.py:25`, with the OpenAPI of `target_openapi.py`).
3. `serve` (`app/server.py:9`) → `uvicorn.run` (`log_config=None`, no `server`/`date` headers).
4. `lifespan` (`app/main.py:58`): `configure_logging`, `start_telemetry`, then
   `app.state.rules = load_rules(...)` (`app/rules/response_rules.py:24`):
   - `load_schema` (`app/rules/schema.py:19`): a JSON object, `validator_for` (the draft it declares), `check_schema`;
   - `load_field_paths` (`app/rules/field_paths.py:21`) twice: a JSON list of strings, each parsed by `parse_field_path`
     (`:33`); a path ending in `[*]` is refused;
   - `error_body_limits` (`app/rules/schema_limits.py:19`): the smallest `maxLength` of `$.error`, `$.rule`, `$.field`,
     `$.reason[*]` and `maxItems` of `$.reason` over every branch (`nodes_at`, `with_alternatives`: `$ref` inside
     the file, `anyOf`/`oneOf`/`allOf`, `properties`/`patternProperties`/`additionalProperties`,
     `items`/`additionalItems`). No limit → `SchemaLoadError`; a `$ref` loop (`RecursionError`) → "the schema refers
     to itself".
   - then `check_own_answers` (`app/failures/own_answers_check.py:18`): at least one part of one character; every
     error code, every rule (the two configured ones and every keyword of the draft), the unsent message and the
     `...` prefix fit; a worst-case sample body (`sample_details`) passes the schema (`schema_problems`). Else
     `SchemaLoadError`.
   Any of these stops the start: a service that could write an error body the firewall blocks must not run.
   Today the limits are 256 / 256 / 256 / 256 / 500.
5. Shutdown: `stop_telemetry`, `reset_logging`.

## File map

| File | Contents |
|---|---|
| `app/main.py` | `create_app(settings)` (`:31`), `excluded_urls(paths)` (`:53`, anchored regexes for `FastAPIInstrumentor`), `lifespan(app)` (`:58`) |
| `app/server.py` | `serve(app, settings)` → `uvicorn.run` |
| `app/telemetry.py` | `build_tracer_provider` (OTLP exporter only when `telemetry.export_enabled`), `start_telemetry` (`LoggingInstrumentor` with `enable_log_auto_instrumentation=False`, `TraceResponsePropagator`, `RequestsInstrumentor`), `stop_telemetry` |
| `app/state.py` | `settings_of`, `rules_of`, `tracer_provider_of`: the one place that reads `app.state`, each checks the type and returns it typed |
| `app/access.py` | `check_access(header_value, settings)` and `expected_credentials(settings)`: not decorated, they hold the password; `login_challenge(settings)`: the `www-authenticate` value, used by the 401 handler and by `/docs` |
| `app/target/client.py` | `send_to_target` (total timeout, `@log_info` only), `call_target` (not decorated), `classified_error`, `was_not_sent`, `returned_headers`; `urllib3.disable_warnings(InsecureRequestWarning)` at import |
| `app/target/response_builder.py` | `build_response(target_response, rules, settings)`, `too_deep(settings)` |
| `app/rules/response_rules.py` | `ResponseRules` (`schema_validator`, `ignored_fields`, `redacted_fields`, `error_limits`), `load_rules(settings)` |
| `app/rules/schema.py` | `load_schema(path)`, `validate_body(body, schema, redacted_fields, redacted_reason)`, `violation_at`, `every_error` (looks into `anyOf` context), `first_violation` (used by the startup check) |
| `app/rules/schema_limits.py` | `error_body_limits(schema, path)`, `smallest_limit`, `nodes_at`, `with_alternatives`, `referenced`, `children`, `property_schemas`, `item_schemas`, `schema_list`; `SchemaNode` |
| `app/rules/field_paths.py` | `FieldPath`, `ROOT` (`$`), `ALL_ITEMS` (`[*]`), `load_field_paths(path)`, `parse_field_path(field, path)`, `remove_fields(body, field_paths)`, `without_field`, `without_field_in_items` |
| `app/rules/json_reading.py` | `read_json_file(path, error)` (one of the runtime files; raises the given `ConfigFileLoadError`), `read_json_body(content)` (strict: `NaN`/`Infinity` refused by `refuse_constant`) |
| `app/models.py` | `FrozenModel`; `checked_http_url` (an `AnyHttpUrl` check that keeps the URL as received); `TargetRequest` (`method`: an HTTP token; `url`; `headers`, `repr=False`; `body`); `Answer` (status, headers, content: the target's answer or one the service writes); `FailureBody` (`error`, `rule`, `field`, `reason: list[str]`, with the descriptions `/docs` shows); `FailureDetails` (the same, `reason: str`, whole) → `FailureRecord` (+ `method`, `url`, `target_status_code`, `target_response`); `ErrorBodyLimits`; `HealthStatus` |
| `app/errors.py` | `ClusterClientError` → `ConfigFileLoadError` (→ `SchemaLoadError`, `FieldPathsLoadError`), `NonStandardJsonError` (also a `ValueError`), `AccessDeniedError`, `RequestFailedError(reason, field, rule)` → `TargetUnreachableError` (→ `ConnectionFailedError`, `NoResponseError`), `InvalidTargetRequestError`, `ResponseRejectedError` |
| `app/routes/target_routes.py` | `build_target_router(settings)`, `require_access(request)`, `target_endpoint(request, body)` |
| `app/routes/read_request.py` | `read_body` (async, see below), `read_target_request(headers, body, settings)`, `header_of_field(settings)` (`{"method": ..., "url": ...}`), `named_by_header(error, headers_by_field)` |
| `app/routes/target_openapi.py` | The OpenAPI of `POST /`, all from the settings: `BasicAuthDocumentation` (shows HTTP Basic in `/docs`, checks nothing), `failure_responses`, `documented_failure(status, error_codes, settings)` (adds `x-edge-target-status` on the rejected status and `www-authenticate` on 401), `trace_response_header` (`traceresponse` and `access-control-expose-headers`, on every answer), `request_documentation`, `trace_request_header`, `forwarding_rule`, `target_request_headers`, `documented_target_headers` |
| `app/routes/health_routes.py` | `health_router`: `report_alive` (`/health/live`), `report_ready` (`/health/ready`); both return `up` |
| `app/failures/answers.py` | `failed_request_answer`, `failure_code`, `failure_codes(settings)` (every configured `FailureCode`; also used by `/docs` and the startup check), `failure_record`, `redacted_content`, `logged_answer` (the one place that logs a failure and builds its answer) |
| `app/failures/body.py` | `failure_body(details, limits, settings)`, `reason_parts`, `shortened_field` |
| `app/failures/exception_handlers.py` | `refused_request_response` (its reason is `reason_text`: a string as is, a list of refusals as JSON), `reason_text`, `access_denied_response`, `internal_error_response`, `own_failure_answer` |
| `app/failures/own_answers_check.py` | `check_own_answers(rules, settings)`, `too_long`, `sample_details`, `schema_problems` |
| `app/logger/decorators.py` | `log_debug`, `log_info(inputs, outputs)`, and their helpers (`read_argument` and `read_path` give `None` for a wrong path, so logging never breaks a call) `line_of` (the INFO line: name, inputs, `-> outputs` only when there are any, duration), `pick_inputs`, `read_argument`, `read_path`, `joined`, `wrap_call`, `elapsed_ms` |
| `app/logger/setup.py` | `configure_logging(settings)`, `reset_logging()`, `install` (adds a `QuietRequestFilter` to every handler) |
| `app/logger/handlers.py` | `console_handler`, `file_handler` (rotating, creates the folder), `prepare_handler` |
| `app/logger/formatters.py` | `JsonFormatter`, `payload_of` (`timestamp`, `level`, `logger`, `message`, `trace_id`, `span_id`, `extra`, `exception`), `trace_fields_of`, `extra_fields_of`, `LineFormatter` with `with_trace_placeholders` (a line outside a trace shows `-`, on a copy of the record), `build_formatter` |
| `app/logger/quiet.py` | `quiet_request` (context variable), `QuietPathsMiddleware` (marks a request to `log.quiet_paths`), `QuietRequestFilter` (drops a quiet request's records below `log.quiet_kept_level`, uvicorn's access line included) |
| `app/config/` | **Every** setting; see "Config" below and `docs/configuration.md` |
| `run_local.py` | Local run: `NoEnvFileSettings` written in code (`manager` / `local-password`, `0.0.0.0:8000`, DEBUG, `logs/local.log`, `logs/local-failures.log`) |
| `docker/entrypoint.py`, `docker/Dockerfile` | Container run: `Settings()` from env. Two-stage image, `uv sync --no-dev`, non-root user, env for host, port, the five paths |
| `helm/files/*.json` | The three runtime files, one copy only: local default path, tests, and the Helm files ConfigMap (never baked into the image) |
| `helm/` | OpenShift chart; see `docs/deployment.md`. `values.schema.json` restricts every value |
| `tests/` | See "Tests" |

`app/config/`: import layers `constants` → `base | field_types` → sections → `settings` (the `config layers` contract).

| File | Contents |
|---|---|
| `constants.py` | Fixed values several files use: `TEXT_ENCODING`, `DISTRIBUTION_NAME`, `HTTP_TCHAR_PATTERN`. A fixed value with one user sits at the top of that file (`MAX_PORT` in `field_types.py`, `BASIC_USERNAME_PATTERN` in `access.py`, `ENV_PREFIX` in `settings.py`) |
| `field_types.py` | `to_upper`, `to_lower`, `HeaderName`, `LowercaseHeaderName`, `LogLevel`, `ErrorStatusCode`, `Port` |
| `base.py` | `BaseConfig`: the frozen `BaseModel` every section extends, `extra="forbid"`; sections never read env |
| sections | `server.py` `ServerSettings`, `application.py` `ApplicationSettings`, `access.py` `AccessSettings`, `headers.py` `HeaderSettings` (`known_placeholders`), `forwarding.py` `ForwardingSettings` (`connect_within_the_total`), `validation.py` `ValidationSettings`, `failures.py` `FailureCode`, `FailureSettings` (`known_placeholders`), `logging.py` `LogFormat`, `HandlerSettings` → `FileSettings` → `FailureFileSettings`, `FormattingSettings`, `LoggingSettings`, `telemetry.py` `TelemetrySettings`. A section never imports another |
| `settings.py` | `Settings`, the only `BaseSettings` (env prefix `CLUSTER_CLIENT_`, nested `__`, `.env`, `own_headers_keep_their_prefixes`); `NoEnvFileSettings` ignores `.env` |

## Mandatory coding rules (the owner enforces these strictly)

1. **Keyword-only everything**: every parameter after `*`, every call by keyword (`f(a=1)`), including library
   calls where possible. Only framework-fixed signatures stay positional (ASGI `__call__`, `logging.Filter.filter`,
   `Formatter.format`, middleware `__init__(app, ...)`, exception handlers). Tests and fixtures are exempt from the `*`.
2. **Type hints on everything**, including local variables (`x: int = ...`).
3. **Pydantic only** for data (no dataclasses). Models extend `FrozenModel`, config sections `BaseConfig`, the root
   `Settings` is the only `BaseSettings`.
4. **Logging by decorator**: every function gets `@log_debug` (all arguments in, result or error out). Key steps
   also get `@log_info(inputs=(...), outputs=(...))` (today: `load_schema`, `load_field_paths`, `error_body_limits`,
   `check_own_answers`, `send_to_target`, `target_endpoint`). Write a log call by hand only when the message needs
   data from inside the function: the failure WARNING/ERROR of `logged_answer` (`answers.py:112`) and the DEBUG line
   of `validate_body` with the original schema message (`schema.py:42`). **Exceptions:**
   - functions whose arguments or result hold a password get no `@log_debug`: `check_access` (it receives only the
     access header value), `expected_credentials`, `call_target`, and `send_to_target` (it keeps its `@log_info` of
     method, URL and status). `TargetRequest.headers` has `repr=False`, so a `TargetRequest` passed on never logs
     them. `read_target_request` stays decorated on purpose: its arguments are the one DEBUG line with the target's
     `authorization` and the manager's access header (see the decisions);
   - helpers that run inside a recursion or a loop get no `@log_debug` when their one caller already logs the
     whole input and output (owner's decision 2026-11-17, measured: they repeated the body at every level, about 55
     times its size per request): `without_field`, `without_field_in_items` (under `remove_fields`), `every_error`
     (under `violation_at`), `with_alternatives`, `referenced`, `children`, `property_schemas`, `item_schemas`,
     `schema_list` (under `nodes_at`), `parse_field_path` (under `load_field_paths`);
   - also not decorated: `lifespan` (logging does not exist yet when it starts), `BasicAuthDocumentation.__call__`
     (a library class), `app/logger/`, `app/config/` (the logger imports it), exception constructors, and tests.
5. **Config is the single source** of every name the code expects (header names, status codes, error codes, paths,
   logger names), even standard headers. No string constants in code for these. Route paths in decorators are
   allowed.
6. **Empty `__init__.py`.** Every package has one and it stays empty. Every import names the module that defines
   the name; no re-exports, no `__all__`.
7. **Simplicity over patterns.** Functions, not classes, unless a library requires a class. No speculative
   extension points, no protocols or interfaces with one implementation, no extra layers. One small file per
   concept; inherit where models share fields.
8. **Tools must pass**: `uv run ruff check .` and `uv run ruff format .` (line length 110),
   `uv run basedpyright` (strict, on `app`, `tests`, `docker`, `run_local.py`), `uv run lint-imports` (layers in
   `pyproject.toml`: `app` (with `state` between `failures | target | telemetry` and `access | rules`), and inside it `app.rules`, `app.target` and `app.config`; a new module needs a layer), `uv run pytest`. Pre-commit runs the first four.

## Decisions that look odd but are deliberate

Keep every one of these. Do not "fix" them without the owner.

- **Sync code + `requests`**: chosen for readability. FastAPI runs `def` routes in a thread pool. Only two things stay
  `async` because the libraries demand it: `lifespan` and `read_body` (Starlette reads the raw body only
  asynchronously; a `bytes` Body parameter would be JSON-parsed instead).
- **`verify=False`** to the targets: internal certificates. Do not "fix" it.
- **No `uv.lock` in git**: the lock stores every package's index URL, and the company network installs from a
  different Artifactory than pypi.org, so one lock cannot work in both. Each place resolves `pyproject.toml` against
  its own index; run `uv sync` once after cloning (pre-commit uses `uv run --frozen`).
- **Config** (owner's decision 2026-11-17): only the root `Settings` reads env and `.env`
  (`CLUSTER_CLIENT_<SECTION>__<FIELD>`); a section (`BaseConfig`) never reads env, so a flat name like
  `CLUSTER_CLIENT_URL` changes nothing, and `NoEnvFileSettings` really ignores `.env`. Defaults
  (`nested_model_default_partial_update`): the root gives every section a full default instance; a shape used several
  times (`FailureCode`, `HandlerSettings` → `FileSettings` → `FailureFileSettings`) has no defaults of its own, and its
  parent gives a full instance. One env value (`CLUSTER_CLIENT_FAILURES__REJECTED__STATUS_CODE`) keeps the other
  defaults. A section refuses unknown fields (`extra="forbid"`): a misspelled field stops the start; a name without a
  section is ignored.
- **Headers to the target: a prefix, not a list** (owner's decision 2026-11-16). The tool does not know which headers
  a target needs, and cannot tell the manager's headers from those added on the way (NGINX, DataPower and the
  OpenShift router add `x-forwarded-*`, `forwarded`, `host`, their own credentials). So the manager marks what goes
  to the target: every header that starts with `headers.target_prefix` (`x-target-`) is sent **without the prefix**;
  no other header reaches the target. The tool's own headers (`x-edge-method`, `x-edge-url`) are read, never sent.
  `authorization` to the target is optional (a metrics call may have none). A header exactly `x-target-` (no name), or
  naming a hop-by-hop or framing header (`headers.refused_target_headers`), is refused as `invalid_request`. The access
  header is never forwarded. OpenTelemetry sets `traceparent`. `Settings.own_headers_keep_their_prefixes` stops the
  start when `headers.method`, `headers.url` or `access.header` starts with `headers.target_prefix`, or when
  `failures.error_header` / `failures.target_status_header` does not start with `forwarding.edge_header_prefix`
  (otherwise a target could fake it).
- **`documented_target_headers`** stays: `/docs` needs it for "Try it out". Any other `x-target-*` header is sent too.
- **The method and the URL go as `requests` sends them** (owner's decision 2026-11-17: the manager also uses
  `requests`, so its behaviour is the standard): the method is any HTTP token and the URL any http(s) URL
  (`AnyHttpUrl`, no length limit); `TargetRequest` keeps both as received, and `requests` prepares them (method in
  upper case, URL quoted again). `requests`' own default headers, `trust_env` and userinfo handling are accepted.
- **`cluster` vs `target` in names**: code names that mean the target say `target` (`TargetRequest`,
  `send_to_target`, `target_status_code`, `x-edge-target-status`). Names that mean the service stay
  `cluster-client` (`ClusterClientError`, env prefix `CLUSTER_CLIENT_`, logger `cluster_client.failures`, realm,
  image, Helm).
- **Access** (owner's decision 2026-11-15): one header (`authorization`) with `Basic base64(username:password)`,
  scheme in any case, credentials compared in constant time, checked before the body is read. `/docs` shows it as
  an HTTP Basic login (documentation only). NGINX adds it, DataPower authenticates with it and passes it on; it is
  never sent to the target. Username and password have no defaults: the service does not start without them; in Helm
  they are required in `secret`. Health endpoints stay open (probes). More complex access logic only when the owner
  asks.
- **Response headers**: every target header is returned except `recomputed_response_headers` and any header that
  starts with `x-edge-`: `x-edge-error` means "cluster-client wrote this", so a target can never fake it. uvicorn's own
  `date` and `server` headers are off.
- **Field paths** use the format of a rejection's `field`: `$.a.b`, `[*]` for every list item. Indexes like `[0]` and
  paths ending in `[*]` are refused at startup.
- **Failure file** (`logs/failures.log`, logger `cluster_client.failures`): one JSON line per failure with the whole
  error, the target's body without the redacted fields. A target body that cannot be decoded is written as it is
  (information before security, owner's decision 2026-11-17). DEBUG logs everything, on purpose.
- **The failure file always has the whole error, never cut** (owner's decision 2026-11-14): every failure the service
  answers itself (`invalid_request` and `internal_error` included) is written there with the full `reason` and
  `field`, at WARNING (ERROR for `internal_error`). Only the answer is cut. `internal_error` sends and logs the error
  and its traceback.
- **DEBUG logs the target password** in one place only: the arguments of `read_target_request`. The owner must always
  have one place with the full error and the whole call: the DEBUG file (`CLUSTER_CLIENT_LOG__LEVEL=DEBUG` and
  `CLUSTER_CLIENT_LOG__FILE__ENABLED=true`; off by default, the root level is INFO so no DEBUG line is built when no
  handler writes it). Never clean a secret without keeping it there.
- **Tracing** is OpenTelemetry, no metrics. Find a failure by the `trace_id` of `traceresponse` (the manager's own
  trace id). `LoggingInstrumentor` only adds `otelTraceID`/`otelSpanID` to records. The call to the target runs in a
  worker thread inside a copy of the request's context, so its span keeps the manager's trace. OTLP export is off by
  default.
- **Logs and traces to Elastic** (owner's decision 2026-11-15): the service never talks to Elastic. Helm
  `collector.enabled` adds an OpenTelemetry Collector sidecar: the service writes every line at `collector.logLevel`
  (default DEBUG, passwords included) as JSON to `app.log` (shared `emptyDir`) and sends spans to `127.0.0.1:4318`; the
  collector sends both to Elasticsearch with its own username and password, into `logs-cluster_client.otel-default`
  and `traces-cluster_client.otel-default` (the same in every network). Logs never leave through the service's OTLP
  (`enable_log_auto_instrumentation=False`). The file receiver is `file_log` (its type in collector-contrib 0.164.0;
  `filelog` is the deprecated alias); every component name was checked against 0.164.0. The collector keeps its read
  position in the `collector-state` `emptyDir`, so a restart resends nothing.
- **Quiet paths** (owner's decision 2026-11-15): requests to `log.quiet_paths` (the two probes) write no line below
  `log.quiet_kept_level` (WARNING) in any handler, so their failures still reach the failure file, and get no span.
- `RequestsInstrumentor` patches `requests` in the whole process: a test client using `requests` in the same process
  gets its `traceparent` overwritten.
- **Timeouts** (owner's decision 2026-11-17): `forwarding.timeout_seconds` (28) covers the whole call, connect
  included; then the answer is `timeout` (the request may still run: "maybe done"). The worker thread keeps running
  after that (first suspect if hangs ever appear). `connect_timeout_seconds` (5) must be shorter; a connect timeout
  stays `connection_failed`. 28 is below the manager's own timeout (35 seconds).
- **Errors raised before sending** (any `requests` error that is a `ValueError`) are `invalid_request`: surely not
  sent, and a bug on the manager's side, so no retry.
- The long `reason` text of `requests` errors is kept as is.
- **One refusal at a time**: a model error is reported before a refused header.
- **`/health/ready` answers `up` and checks nothing more** (owner's decision 2026-11-18): uvicorn serves requests
  only after `lifespan` finished, so the schema and field files are loaded and checked; a failed start exits. A
  neutral tool holds no list of targets to check.
- **404 and 405 are not described in `/docs`** (owner's decision 2026-11-17); the general rule (`x-edge-error` on every
  own answer) is in the docs pages.
- **The firewall schema is checked by the draft it declares** (`validator_for`): draft-04 today, the firewall's
  draft, on purpose. Tests use the same real files in `helm/files/` (no copy). The regex engine (Python's, not
  ECMA's) stays until IT answers. JSON that we accept and DataPower might not (duplicate keys, odd UTF-8) is a known,
  accepted gap.
- **Firewall faithfulness**: the firewall accepts only standard JSON, so `NaN`/`Infinity` are rejected as
  `not_json`. A body too deep for Python is rejected (`too_deep`), never a 500. Removing fields copies only the
  changed path. Non-JSON answers stay rejected.
- **Every body the service writes passes the firewall schema** (`helm/files/response-schema.json`, identical to
  `response-schema-depth.json` in redis-enterprise-services; the firewall's limit is 256, documents that say 512 are
  stale). The limits are **computed from the schema at startup** (owner's decisions 2026-11-16 and 2026-11-17), never
  configured: `part_length`, `max_parts`, and the `field`, `error` and `rule` lengths. There is no "no limit": a path
  of the error body without a limit stops the start, and so does a recursive schema. Above `max_parts`, the last part
  says how many characters were not sent; a longer `field` is cut from the start, `...` included. `check_own_answers`
  checks every rule keyword of the draft (owner's decision: stays).
- **The rejection `reason`** (owner's decision 2026-11-13, because of DataPower's character limit): only the
  `redacted_fields` are removed, from a copy of the body; everything else, even an unknown password, goes out in full
  (information first). `rule` and `field` always come from the real failure; `reason` from the copy's failure at the
  same path, else `redacted_reason`. The original message stays in the DEBUG log. `violation_at` looks at every
  failure of the copy, `anyOf` context included. No generic fallback: no `except Exception` around building the
  explanation. `FailureSettings` and `HeaderSettings` refuse texts with unknown placeholders.
- **The runtime files live only in `helm/files/`** (owner's decision 2026-11-15: never two copies). Helm reads only
  inside the chart, so the local default paths point there too. In Helm each file is mounted at its own path
  (`files.*`, `subPath`) and the chart passes the paths, the port and the log paths as env (owner's decision
  2026-11-17); `values.schema.json` forbids those keys in `config`/`secret`. The Dockerfile's env stays the default
  for a run without Helm.
- **One schema, one set of field files per service.** For another technology, first change the schema; change the
  logic only if there is no other choice. Redis-specific defaults stay.
- Rejected simplifications (owner, 2026-11-17): merging the two `try` blocks of `build_response`, merging
  `expected_credentials` into `check_access`, merging the three exception handlers, splitting
  `failed_request_answer`.

## Tests

- **Unit tests only, on the main logic.** No integration or E2E tests, no tests of code that only connects parts, no
  coverage gate. One assertion and one behaviour per test.
- **Test only this project's logic. Never test library behaviour** (Pydantic validation, env parsing, logging
  propagation, SecretStr masking...). Ask: "if this fails, is the bug in our code?" If not, do not write it.
- The target is faked by replacing `app.target.client.requests.request` (`tests/support/fake_target_api.py`, the
  `fake_target` fixture in `tests/conftest.py`).
- The schema and the field files are the real ones in `helm/files/` (`tests/support/rules.py`, `RULES`); small test
  schemas declare draft-04 and go through `validator_for` like the code.
- `tests/support/cluster_samples/`: 43 real Redis Enterprise answers, passwords replaced; `tests/unit/rules/test_samples.py`
  runs every one through the real files.
- Layout: `tests/unit/` mirrors `app/`: `config/`, `routes/`, `rules/`, `target/`, `failures/`, `logger/`, and `test_access.py` / `test_state.py`
  for the top-level `access.py` / `state.py`; one file per module or concept. 235 tests today.
- Run: `uv run pytest`.

## Diagrams and docs

- `docs/diagrams/`: `context`, `flow`, `sequence`, `class-diagram` (modules), `startup`, `deployment`. Each is a
  `.drawio` and a `.drawio.png` exported from it (`drawio -x -f png -e -b 20 -o <name>.drawio.png <name>.drawio`).
- When a code change makes a diagram or a page in `docs/` wrong, update it in the same task (edit the cells in place,
  keep the layout, export the PNG again and look at it). Do not touch diagrams for changes they do not show.
- `docs/proposals/` is history; do not update it.
- `README.md` holds installation and usage only, no code explanations.

## Working with the owner

- The owner writes in Hebrew. Keep answers short.
- A question ("why...?", "what is...?") is **not** a request to change code. Answer, propose, wait for "yes".
- Several decisions: ask one plain question per message.
- **Never commit** unless explicitly asked. Conventional Commits.
- Do not invent facts; what is an owner's decision, ask.

## Open items (do not implement without the owner)

- A header sent twice (two `x-target-*` with the same name) reaches the target with its first value only
  (`dict(request.headers)`). The same holds for the answer: `returned_headers` builds a `dict[str, str]`, so a header
  the target sends several times (e.g. `Set-Cookie`) reaches the manager as one comma-joined value. To check: how
  complicated it is to keep every value, in both directions.
- Secrets in ignored fields (`$.api_key`, `$.cm_key`, `$.access_token`, ...) are removed from the answer but not from
  the failure file: when such an answer is rejected for another field, `target_response` holds them (also on stdout in
  Helm, where the console is JSON). Fix in `redacted-fields.json`, or decide otherwise. Waiting for a separate PR.
- `check_own_answers` tests only the largest error body. A schema that requires `rule`, or puts a `pattern` on
  `reason[*]` or `field`, can pass the startup check and still block a smaller or more varied own answer. Waiting for
  a separate PR.
