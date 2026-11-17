# AGENTS.md — how this code works and how to change it

Read this whole file before touching anything. It replaces the conversation history you do not have.

## What the service is

`cluster-client` runs inside every firewalled network. A **manager** in another network sends it one HTTP
request; cluster-client sends it to the **target** named in that request (today the Redis Enterprise REST API of a
cluster; tomorrow any HTTP API), checks the answer, and returns it. It is deliberately "dumb" and
technology-neutral: the manager owns all business logic, and another technology changes only the three JSON files.

The only intervention is so the answer passes the firewall: known useless fields are removed, then the answer
must match one JSON Schema. Otherwise the target's answer (status, headers, body) is returned **unchanged, byte
for byte**. cluster-client never "fixes" an answer.

## The request flow (the whole program)

`POST /` → `app/routes/target_routes.py::target_endpoint` is the orchestrator. Read it first; every step is
one visible call:

1. OpenTelemetry (`FastAPIInstrumentor`, `app/telemetry.py`) continues the manager's `traceparent` (or starts a trace).
2. `require_access`, a route dependency that runs before the body is read, passes the value of the access header
   (`authorization`) to `check_access` (`app/access.py`), which compares it with `Basic base64(username:password)` from
   `settings.access`. Missing/wrong → `AccessDeniedError` → HTTP 401 with `x-edge-error: unauthorized`. Nothing
   is sent to the target.
3. `read_target_request` (`app/routes/read_request.py`) turns the incoming headers + body into a `TargetRequest`:
   `x-edge-method` and `x-edge-url` (the tool's own headers: read, never sent), and every header that starts with
   `x-target-`, without the prefix. Missing/invalid own header, or an `x-target-` header in
   `headers.refused_target_headers` (hop-by-hop and framing: `host`, `content-length`, …) → HTTP 400 with
   `x-edge-error: invalid_request`. Nothing is sent to the target.
4. `send_to_target` (`app/target_client.py`) calls the target with `requests` in a worker thread and waits at most
   `forwarding.timeout_seconds` for the whole call; `RequestsInstrumentor` adds `traceparent`. A `requests` error
   that is also a `ValueError` (invalid URL or header: refused before sending) → `InvalidTargetRequestError`
   (`invalid_request`); `ConnectionFailedError` when the request surely did not leave (`requests` wraps it in
   `MaxRetryError`: refused, DNS, connect timeout); else `NoResponseError` (total timeout, read timeout,
   connection cut, any TLS error: it can happen after the target got the request).
5. `build_response` (`app/response_builder.py`):
   - empty body (e.g. 204) → returned as is;
   - decode JSON strictly (`read_json_body`: not JSON, `NaN`/`Infinity` → `ResponseRejectedError`, rule
     `not_json_rule`, field `$`);
   - `remove_fields` (`app/field_paths.py`) removes the configured ignored field paths ("function X"); it copies
     only along the removed paths and returns the same object when nothing was removed;
   - `validate_body` (`app/schema.py`) checks the JSON Schema (violation → `ResponseRejectedError` with the
     failing `rule` and field, e.g. `$.uid`, and a `reason` built from a copy without the redacted fields);
   - a body nested too deeply for Python (`RecursionError`) → `ResponseRejectedError`, rule `too_deep_rule`;
   - if X removed nothing → the **original** response object is returned; else the body is re-encoded.
6. On any `RequestFailedError`: `failed_request_answer` (`app/failures/answers.py`) picks the `FailureCode` once,
   builds the `FailureRecord` once (the target's answer without the redacted fields), and `logged_answer` writes
   it whole to the failure log file and builds the answer: `x-edge-error`, and when the target answered,
   `x-edge-target-status`; only the answer is cut (`failure_body`, `app/failures/body.py`). Anything else the
   service answers itself goes through the handlers of `app/failures/exception_handlers.py` and the same `logged_answer`,
   so every such answer has `x-edge-error`: `AccessDeniedError` → `unauthorized`; `HTTPException` (bad headers,
   wrong path, wrong method) → `invalid_request`; any other exception → `internal_error`.
7. The route returns status + headers + body; OpenTelemetry adds `traceresponse`.

Diagrams of exactly this flow: `docs/diagrams/flow.drawio` (activity) and `docs/diagrams/class-diagram.drawio`.

## File map

| File | Contents |
|---|---|
| `app/main.py` | `create_app(settings)` (factory: builds the app's `TracerProvider`, `FastAPIInstrumentor`) and `lifespan` (startup: configure logging, start telemetry, load the `ResponseRules` into `app.state.rules`, `check_own_answers`; shutdown: stop telemetry) |
| `app/server.py` | `serve()` → `uvicorn.run` |
| `app/telemetry.py` | `build_tracer_provider` (one per app, never global), `start_telemetry` / `stop_telemetry`: instrument and uninstrument `requests` and logs |
| `app/config/` | **every** setting. Import layers `constants` → `field_types` and `base` → sections → `settings` (enforced by the `config layers` contract): `constants.py` (fixed values nobody may change that several files use: `TEXT_ENCODING`, `DISTRIBUTION_NAME`, `HTTP_TCHAR_PATTERN`; a fixed value with one user sits at the top of that file, e.g. `MAX_PORT` in `field_types.py`, `BASIC_USERNAME_PATTERN` in `access.py`, `ENV_PREFIX` in `settings.py`), `field_types.py` (`to_upper`, `to_lower`, `HeaderName`, `LowercaseHeaderName`, `LogLevel`, `ErrorStatusCode`, `Port`), `base.py` (`BaseConfig`: the frozen `BaseModel` every section extends, `extra="forbid"`; sections never read env), one file per section (`server.py`, `application.py`, `access.py`, `headers.py`, `forwarding.py`, `validation.py`, `failures.py`, `logging.py`, `telemetry.py`; a section never imports another), `settings.py` (root `Settings`, the only `BaseSettings`: env prefix `CLUSTER_CLIENT_`, nested `__`, `.env`; `NoEnvFileSettings` ignores `.env`) |
| `app/models.py` | `FrozenModel` (base of the data models), `TargetRequest` (method: any HTTP token; url: checked as an http(s) URL, kept as received; headers; body), `Answer` (status, headers, content: the target's answer or one the service writes itself), `FailureBody`, `FailureDetails`, `FailureRecord`, `ErrorBodyLimits`, `HealthStatus` |
| `app/errors.py` | `ClusterClientError` → `AccessDeniedError`, `NonStandardJsonError`, `ConfigFileLoadError` (→ `SchemaLoadError`, `FieldPathsLoadError`), `RequestFailedError` → `TargetUnreachableError` (→ `ConnectionFailedError`, `NoResponseError`), `InvalidTargetRequestError`, `ResponseRejectedError` |
| `app/routes/target_routes.py` | `build_target_router(settings)`, `require_access` (dependency of `POST /`) and the `POST /` orchestrator `target_endpoint` |
| `app/routes/target_openapi.py` | the OpenAPI of `POST /` from the settings: the forwarding rule, the own headers, the documented `x-target-*` headers, every failure status with `FailureBody` and its headers |
| `app/routes/read_request.py` | `read_body` (async, see below), `read_target_request` (own headers, `x-target-*` without the prefix, refused headers), `header_of_field`, `named_by_header` |
| `app/routes/health_routes.py` | `/health/live`, `/health/ready` (both return `up`; real readiness is a TODO) |
| `app/access.py` | `check_access` (gets only the access header value) and `expected_credentials`, both not decorated: they hold the password; `login_challenge` (the `www-authenticate` value, sent on 401 and shown in `/docs`) |
| `app/target_client.py` | `send_to_target` (total timeout), `call_target`, `classified_error`, `was_not_sent`, `returned_headers` |
| `app/response_builder.py` | `build_response(target_response, rules, settings)`, `too_deep` |
| `app/rules.py` | `ResponseRules` (schema validator, ignored and redacted fields, `error_limits`) and `load_rules` |
| `app/json_reading.py` | `read_json_file` (reads one of the runtime JSON files), `read_json_body` (strict: `NaN`/`Infinity` refused) |
| `app/field_paths.py` | `load_field_paths`, `parse_field_path`, `remove_fields`, `without_field`, `without_field_in_items` (used for ignored and redacted fields) |
| `app/schema.py` | `load_schema` (`validator_for`: the draft the schema declares), `validate_body`, `violation_at`, `every_error`, `first_violation` |
| `app/schema_limits.py` | `error_body_limits`: walks the schema (`$ref` inside the file, `anyOf`/`oneOf`/`allOf`, `properties`/`patternProperties`/`additionalProperties`, `items`) along the field paths of our own error body (`$.error`, `$.rule`, `$.field`, `$.reason`, `$.reason[*]`, parsed by `parse_field_path`); the smallest limit of all branches wins; a path without a limit stops the start |
| `app/failures/` | `answers.py` (`failed_request_answer`, `failure_code`, `failure_codes` (every configured `FailureCode`), `failure_record`, `redacted_content`, `logged_answer`: the one place that logs a failure and builds its answer), `body.py` (`failure_body`, `reason_parts`, `shortened_field`), `own_answers_check.py` (`check_own_answers`: startup check that the schema holds every own answer), `exception_handlers.py` (`refused_request_response`, `access_denied_response` (adds the `www-authenticate` challenge), `internal_error_response`, `own_failure_answer`) |
| `app/logger/formatters.py` | JSON + line formatters |
| `app/logger/handlers.py` | terminal / file handlers |
| `app/logger/setup.py` | `configure_logging`, `reset_logging` |
| `app/logger/decorators.py` | `log_debug`, `log_info` |
| `app/logger/quiet.py` | `QuietPathsMiddleware` (marks a request to `log.quiet_paths` in the `quiet_request` context variable), `QuietRequestFilter` (on every handler: drops its records below `log.quiet_kept_level`, uvicorn's access line included; failures stay) |
| `run_local.py` / `docker/entrypoint.py` | local run with settings in code / container run with settings from env |
| `helm/files/response-schema.json`, `helm/files/ignored-fields.json`, `helm/files/redacted-fields.json` | the three runtime files, one copy only: the local default path, the tests, and the Helm files ConfigMap (never baked into the image) |
| `helm/` | OpenShift chart: Deployment, Service, Route, ConfigMap and Secret (keys only from `config` / `secret` in values), files ConfigMap (every `helm/files/*.json`, as is), optional collector sidecar (`collector.*`). One values file per network in `helm/networks/` (`domain`, optional `image.tag` / `route.host`); `_helpers.tpl` builds the image and route host from `domain`. `values.schema.json` restricts every chart value; `config`/`secret` keys must be `CLUSTER_CLIENT_*` strings, minus those the image owns (host, port); the service checks their values, and every field name inside a section, when it starts |
| `tests/support/cluster_samples/` | real Redis Enterprise answers, passwords replaced; every one must pass the real `helm/files` (`tests/unit/test_samples.py`) |

## Mandatory coding rules (the owner enforces these strictly)

1. **Keyword-only everything**: every parameter after `*`, every call by keyword (`f(a=1)`), including library
   calls where possible. Only framework-fixed signatures stay positional (ASGI `__call__`, `logging.Filter.filter`,
   `Formatter.format`, middleware `__init__(app, ...)`, exception handlers). Tests and fixtures are exempt from the `*`.
2. **Type hints on everything**, including local variables (`x: int = ...`).
3. **Pydantic only** for data (no dataclasses). Models extend `FrozenModel`, config sections `BaseConfig`, the root `Settings` is the only `BaseSettings`.
4. **Logging by decorator**: every function gets `@log_debug` (all arguments in, result or error out). Key steps
   also get `@log_info(inputs=(...), outputs=(...))`. Write a log call by hand only when the message needs data from
   inside the function (the failure WARNING/ERROR of `logged_answer`, and the DEBUG line of `validate_body` with
   the original schema message). **Exception:** functions whose arguments or result hold a password get no
   `@log_debug` (`check_access`, which receives only the value of the access header, `expected_credentials`,
   `call_target`, and `send_to_target`, which keeps its `@log_info` of method, URL and status);
   `TargetRequest.headers` is left out of its repr (`repr=False`), so a `TargetRequest` passed to another function
   never logs them; `read_target_request` stays decorated on purpose: its arguments are the one DEBUG line with
   the target's `authorization` and the manager's access header (see below). Also not decorated: `lifespan` (logging
   does not exist yet when it starts, so its lines are lost), `app/logger/`, `app/config/` (the logger imports it),
   exception constructors, and tests.
5. **Config is the single source** of every name the code expects (header names, status codes, error codes, paths,
   logger names). No string constants in code for these. Route paths in decorators are allowed.
6. **Empty `__init__.py`.** Every package has one and it stays empty. Every import names the module that defines
   the name; no re-exports, no `__all__`.
7. **Simplicity over patterns.** Functions, not classes, unless a library requires a class. No speculative
   extension points, no protocols/interfaces with one implementation, no extra layers. One small file per
   concept; inherit where models share fields.
8. Ruff must pass (`ruff check . && ruff format .`), line length 110. `basedpyright` must pass in strict mode on `app` and `tests`. `lint-imports` must pass (layers in `pyproject.toml`; a new module needs a layer).

## Decisions that look odd but are deliberate

- **Sync code + `requests`**: the owner chose sync for readability. FastAPI runs `def` routes in a thread pool.
  Only two things stay `async` because the libraries demand it: `lifespan` and `read_body`
  (Starlette reads the raw body only asynchronously; a `bytes` Body parameter would be JSON-parsed instead).
- **`verify=False`** to the targets is intentional (internal certificates). Do not "fix" it.
- **No `uv.lock` in git**: the lock stores every package's index URL, and the company network installs from a
  different artifactory than pypi.org, so one lock cannot work in both. Each place resolves `pyproject.toml`
  against its own index; run `uv sync` once after cloning (pre-commit uses `uv run --frozen`).
- **Config** (owner's decision 2026-11-17): only the root `Settings` reads env and `.env`
  (`CLUSTER_CLIENT_<SECTION>__<FIELD>`); a section (`BaseConfig`, a plain frozen model) never reads env, so a flat
  name like `CLUSTER_CLIENT_URL` changes nothing, and `NoEnvFileSettings` really ignores `.env`. Defaults
  (pydantic-settings `nested_model_default_partial_update`): the root gives every section a full default instance;
  a shape used several times (`FailureCode`, `HandlerSettings` → `FileSettings` → `FailureFileSettings`) has no
  defaults of its own, and its parent gives a full instance. One ENV value
  (`CLUSTER_CLIENT_FAILURES__REJECTED__STATUS_CODE`) keeps the other defaults. A section refuses unknown fields
  (`extra="forbid"`, owner's decision 2026-11-17), so `CLUSTER_CLIENT_FORWARDING__TIMEOUT_SECOND` (misspelled)
  stops the start; a name without a section (`CLUSTER_CLIENT_FOO`) is still ignored.
- **Headers to the target: a prefix, not a list** (owner's decision 2026-11-16). The tool is technology-neutral,
  so it does not know which headers a target needs, and it cannot tell the manager's headers from those added on
  the way (NGINX, DataPower, the OpenShift router add `x-forwarded-*`, `forwarded`, `host`, their own
  credentials…). So the manager marks what goes to the target: every incoming header that starts with
  `headers.target_prefix` (`x-target-`) is sent **without the prefix** (`x-target-authorization` →
  `authorization`, `x-target-cluster-state-id` → `cluster-state-id`); no other incoming header reaches the target.
  The tool's own headers have their own prefix (`x-edge-method`, `x-edge-url`, like `x-edge-error`): read,
  never sent. `authorization` to the target is optional (a metrics call may have none). An `x-target-` header
  naming a hop-by-hop or framing header (`headers.refused_target_headers`) is refused as `invalid_request`.
  The access header (`settings.access.header`) is never forwarded. OpenTelemetry sets `traceparent`.
- **The method and the URL go as `requests` sends them** (contract C1; owner's decision 2026-11-17: the manager
  also uses `requests`, so its behaviour is the standard): the method is any HTTP token and the URL any http(s)
  URL (`AnyHttpUrl` checks it, no length limit); `TargetRequest` keeps both as received, never pydantic's
  normalized form, and `requests` prepares them as it does for any caller (the method in upper case, the URL
  re-quoted).
- **`cluster` vs `target` in names**: code names that mean the target say `target` (`TargetRequest`,
  `send_to_target`, `target_status_code`, `x-edge-target-status`). Names that mean the service stay
  `cluster-client` (`ClusterClientError`, env prefix `CLUSTER_CLIENT_`, logger `cluster_client.failures`, realm,
  image, Helm).
- **Access to the cluster client** (owner's decision 2026-11-15): one header (`settings.access.header`,
  `authorization`, the standard header) with `Basic base64(username:password)` (scheme in any case, credentials
  compared in constant time), checked by the `require_access` dependency before the body is read. `/docs` shows
  it as an HTTP Basic login (`BasicAuthDocumentation`, documentation only: it checks nothing). NGINX adds it,
  the DataPower in front authenticates with the same header and passes it on; it is never sent to the target
  (the target gets its own `authorization` only from `x-target-authorization`). Username and password have no
  defaults: the service does not start without them; in Helm they are required in `secret`. Health endpoints
  stay open (probes). More complex access logic only when the owner asks.
- **Response headers**: all target headers are returned except `recomputed_response_headers` (content-length,
  content-encoding, transfer-encoding, connection) and any header starting with `forwarding.edge_header_prefix`
  (`x-edge-`): `x-edge-error` means "the cluster client wrote this" (contract C9), so a target can never fake it.
  uvicorn's own `date`/`server` headers are off.
- **Ignored field paths** use the same format as the `field` of a rejection: `$.a.b`, `[*]` for every list item
  (`$[*].shards_placement`). Indexes like `[0]` and paths ending in `[*]` are rejected at startup.
- **Failure file** (`logs/failures.log`, logger `cluster_client.failures`): one JSON line per failed request,
  including the target response without the redacted fields (`validation.redacted_fields_path`: the passwords
  Redis returns in bdb and crdb answers). DEBUG logs everything, on purpose.
- **Tracing** is OpenTelemetry. Find a failure by the `trace_id` of the `traceresponse` header (the manager's own
  trace id). `LoggingInstrumentor` only adds `otelTraceID`/`otelSpanID` to records. The call to the target runs
  in a worker thread inside a copy of the request's context, so its span keeps the manager's trace.
- **Logs and traces to Elastic** (owner's decision 2026-11-15): the service never talks to Elastic. Helm
  `collector.enabled` adds an OpenTelemetry Collector sidecar (`configmap-collector.yaml`, `secret-collector.yaml`):
  the service writes every line at `collector.logLevel` (default DEBUG, passwords included) as JSON to
  `logs/app.log` (shared `emptyDir`) and sends spans to `127.0.0.1:4318`; the collector reads both and sends them
  to Elasticsearch with its own username/password, into the data streams `logs-cluster_client.otel-default`
  and `traces-cluster_client.otel-default` (`data_stream.dataset` resource attribute): one place for this service,
  the same in every network (owner's decision). Logs still never leave through the service's OTLP
  (`enable_log_auto_instrumentation=False`). The owner will remove secrets before they are logged when needed.
  The file receiver is `file_log`: its type in collector-contrib 0.164.0 (`filelog` is the deprecated alias).
- **Quiet paths** (owner's decision 2026-11-15): requests to `log.quiet_paths` (default the two probes) write no
  log line below `log.quiet_kept_level` (WARNING) in any handler, so their failures still reach the failure file,
  and get no span (`excluded_urls` of `FastAPIInstrumentor`, anchored to the exact path), so the probes do not
  flood the terminal and Elastic.
- `RequestsInstrumentor` patches `requests` in the whole process: a test client using `requests` in the same
  process gets its `traceparent` overwritten.
- **Timeouts** (owner's decision 2026-11-17): `forwarding.timeout_seconds` (28) covers the whole call to the
  target, connect included: `send_to_target` waits for the worker thread at most that long, then answers
  `timeout` (the request may still be running, so "maybe done"). `connect_timeout_seconds` (5) must be shorter;
  a connect timeout stays `connection_failed`. 28 is kept below the manager's own timeout (35 seconds, contract C15).
- **Errors raised before sending** (invalid URL or header, any `requests` error that is a `ValueError`) are
  `invalid_request`: surely not sent, and a bug on the manager's side, so no retry (contract §1).
- The error `reason` from `requests` is long; the owner chose to keep it as is.
- **DEBUG logs the target password** in one place only: the arguments of `read_target_request` (it receives every
  header, the manager's access header included); `check_access` gets only the access header and is not decorated,
  and `TargetRequest.headers` has `repr=False`. The owner chose this;
  do not "fix" it. The owner must always have one place with the full error and the whole call: the DEBUG file log
  (`CLUSTER_CLIENT_LOG__FILE__ENABLED=true`, off by default). Never clean a secret without keeping it there.
- **The firewall schema is checked by the draft it declares** (`validator_for`): draft-04 today, the firewall's
  draft, on purpose. Tests use the same real files in `helm/files/` (no copy).
- **Firewall faithfulness**: the firewall accepts only standard JSON, so `NaN`/`Infinity` in a target body are
  rejected as `not_json`. A body too deep for Python is rejected (`too_deep`), never a 500. Removing fields copies
  only the changed path, so a deep body is never copied whole.
- **Every body the service writes itself passes the firewall schema** (`helm/files/response-schema.json`, identical
  to `response-schema-depth.json` in redis-enterprise-services): `{"error", "rule", "field", "reason"}`, `reason`
  a list of parts. The limits are **computed from the schema at startup** (`error_body_limits`, owner's decision
  2026-11-16), never configured: `part_length` = `maxLength` of `$.reason[*]` (256 today), `max_parts` =
  `maxItems` of `$.reason` (500), the `field` limit = `maxLength` of `$.field` (256), and the same for `error` and
  `rule` (owner's decision 2026-11-17): there is no "no limit"; a path of the error body without a limit stops the
  start, and so does a recursive schema (forbidden: a `$ref` to the root `#` finds no limit, a `$ref` loop is
  reported as a schema that refers to itself). Above `max_parts`, the last
  part says how many characters were not sent; a longer `field` is cut from the start, `...` included.
  `check_own_answers` stops the start when the schema cannot hold an own answer: an error code, a rule (configured
  or a keyword of the schema's draft), the unsent message or the `...` prefix too long, or a worst-case sample
  body breaking the schema.
- **The rejection `reason`** (owner's decision 2026-11-13, because of the character limit of DataPower): only the
  `redacted_fields` are removed, from a copy of the body; everything else, even an unknown password, goes out in
  full. `rule` and `field` always come from the real failure; `reason` comes from the copy's failure at the same
  path, else it is `redacted_reason`. The original `error.message`, with the password, stays in the DEBUG log (a
  hand-written line in `validate_body`). `violation_at` looks at every failure of the copy, `anyOf` context
  included, without `best_match` descending again. No generic fallback: no `except Exception` around building the
  explanation. `FailureSettings` refuses texts with unknown placeholders.
- **The failure file always has the whole error, never cut** (owner's decision 2026-11-14): every failure the
  service answers itself (`invalid_request` and `internal_error` included) is written there with the full
  `reason` and `field`, at WARNING/ERROR, not only at DEBUG. Only the answer is cut to the firewall limits.
  `internal_error` sends and logs the error and its traceback.
- **The runtime files live only in `helm/files/`** (owner's decision 2026-11-15: never two copies). Helm reads
  only inside the chart, so the local run's default paths point there too; the container gets them at
  `/etc/cluster-client/` (env in the Dockerfile). The collector keeps its read offset of `app.log` in the
  `collector-state` `emptyDir` (`file_storage`), so a collector restart resends nothing.
- **One schema, one set of field files per service.** More technologies later: first change the schema, change
  the logic only if there is no other choice. Non-JSON answers stay rejected, Redis-specific defaults stay.

## Tests

- **Unit tests only, on the main logic.** No integration or E2E tests, no tests of code that only connects parts, no coverage gate.
- **Test only this project's logic. Never test library behaviour** (Pydantic validation, env parsing, logging
  propagation, SecretStr masking…). Ask: "if this fails, is the bug in our code?" If not, don't write it.
- The target is faked by replacing `app.target_client.requests.request` (`tests/support/fake_target_api.py`,
  `fake_target` fixture). One assertion/behaviour per test.
- The firewall schema and the field files are the real ones in `helm/files/` (`tests/support/rules.py`); local
  test schemas declare draft-04 and go through `validator_for` like the code.
- Run: `pytest`.

## Working with the owner

- A question ("why…?", "what is…?") is **not** a request to change code. Answer, propose, wait for "yes".
- **Never commit** unless explicitly asked. Conventional Commits; single branch `main`.
- When code changes make `docs/diagrams/` stale, update the diagrams in the same task (edit cells in place, keep the
  layout, render to check); do not touch them for changes they do not show.
- Keep answers short; the owner writes in Hebrew.

## Open items (do not implement without the owner)

- `/health/ready` should check something real.
- A header sent twice (two `x-target-*` with the same name) reaches the target with its first value only
  (`dict(request.headers)`). To check (owner, 2026-11-17): how complicated it is to replace `dict[str, str]` with a
  type that keeps every value.
