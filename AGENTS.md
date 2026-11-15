# AGENTS.md — how this code works and how to change it

Read this whole file before touching anything. It replaces the conversation history you do not have.

## What the service is

`cluster-client` runs inside every firewalled network. A **manager** in another network sends it one HTTP
request; cluster-client calls the **Redis Enterprise REST API** of the cluster named in that request, checks
the answer, and returns it. It is deliberately "dumb": the manager owns all business logic.

The only intervention is so the answer passes the firewall: known useless fields are removed, then the answer
must match one JSON Schema. Otherwise the cluster's answer (status, headers, body) is returned **unchanged, byte
for byte**. cluster-client never "fixes" an answer.

## The request flow (the whole program)

`POST /` → `app/routes/cluster_routes.py::cluster_endpoint` is the orchestrator. Read it first; every step is
one visible call:

1. OpenTelemetry (`FastAPIInstrumentor`, `app/telemetry.py`) continues the manager's `traceparent` (or starts a trace).
2. `require_access`, a route dependency that runs before the body is read, calls `check_access` (`app/access.py`), which compares the access header (`authorization`) with
   `Basic base64(username:password)` from `settings.access`. Missing/wrong → `AccessDeniedError` → HTTP 401 with
   `x-edge-error: unauthorized`. Nothing is sent to the cluster.
3. `read_cluster_request` (`app/routes/read_request.py`) turns the incoming headers + body into a
   `ClusterRequest`, including the configured pass-through headers. Missing/invalid header → HTTP 400 with
   `x-edge-error: invalid_request` (from config). Nothing is sent to the cluster.
4. `send_to_cluster` (`app/cluster_client.py`) calls the cluster with `requests`; `RequestsInstrumentor` adds
   `traceparent`. Any `RequestException` →
   `ConnectionFailedError` when the request surely did not leave (`requests` wraps it in `MaxRetryError`:
   refused, DNS, connect timeout), else `NoResponseError` (read timeout, connection cut, any TLS error: it can
   happen after the cluster got the request).
5. `build_response` (`app/response_builder.py`):
   - empty body (e.g. 204) → returned as is;
   - decode JSON (not JSON → `ResponseRejectedError`, rule `not_json_rule`, field `$`);
   - `remove_fields` (`app/field_paths.py`) removes the configured ignored field paths ("function X");
   - `validate_body` (`app/schema.py`) checks the JSON Schema (violation → `ResponseRejectedError` with the
     failing `rule` and field, e.g. `$.uid`, and a `reason` built from a copy without the redacted fields);
   - if X removed nothing → the **original** response object is returned; else the body is re-encoded.
6. On any `RequestFailedError`: `record_failure` writes one JSON line to the failure log file (redacted
   fields left out of the cluster response), then `failure_response` builds the answer with `x-edge-error`,
   and on a rejection `x-edge-cluster-status` (`app/failures/`). Both start from the same `failure_details`; the
   file keeps it whole, only the answer is cut (`failure_body`, `app/failures/reason_parts.py`). Anything else the service answers itself goes
   through the handlers of `app/failures/handlers.py`, so every such answer has `x-edge-error`: `AccessDeniedError` →
   `unauthorized`; `HTTPException` (bad headers, wrong path, wrong method) → `invalid_request`; any other exception → `internal_error`.
7. The route returns status + headers + body; OpenTelemetry adds `traceresponse`.

Diagrams of exactly this flow: `docs/diagrams/flow.drawio` (activity) and `docs/diagrams/class-diagram.drawio`.

## File map

| File | Contents |
|---|---|
| `app/main.py` | `create_app(settings)` (factory: builds the app's `TracerProvider`, `FastAPIInstrumentor`) and `lifespan` (startup: configure logging, start telemetry, load the `ResponseRules` into `app.state.rules`; shutdown: stop telemetry) |
| `app/server.py` | `serve()` → `uvicorn.run` |
| `app/telemetry.py` | `build_tracer_provider` (one per app, never global), `start_telemetry` / `stop_telemetry`: instrument and uninstrument `requests` and logs |
| `app/config/` | **every** setting. Import order `constants` → `utils` → `field_types` → `base` → sections → `settings` (enforced by the `config layers` contract): `constants.py` (fixed values nobody may change: `TEXT_ENCODING`, `DISTRIBUTION_NAME`, env prefix…), `utils.py` (`to_upper`, `to_lower`), `field_types.py` (`HeaderName`, `LogLevel`, `ErrorStatusCode`, `Port`), `base.py` (`BaseConfig`: the one `BaseSettings` every config class extends; frozen, env prefix `CLUSTER_CLIENT_`, nested `__`, `.env`), one file per section (`server.py`, `access.py`, `headers.py`, `forwarding.py`, `validation.py`, `failures.py`, `logging.py`, `telemetry.py`; a section never imports another), `settings.py` (root `Settings`; `NoEnvFileSettings` ignores `.env`) |
| `app/models.py` | `FrozenModel` (base of the data models), `ClusterRequest`, `ClusterResponse`, `FailureBody`, `FailureDetails`, `RequestFailure`, `HttpMethod`, `HealthStatus` |
| `app/errors.py` | `ClusterClientError` → `AccessDeniedError`, `ConfigFileLoadError` (→ `SchemaLoadError`, `FieldPathsLoadError`), `RequestFailedError` → `ClusterUnreachableError` (→ `ConnectionFailedError`, `NoResponseError`), `ResponseRejectedError` |
| `app/routes/cluster_routes.py` | `build_cluster_router(settings)`, `require_access` (dependency of `POST /`) and the `POST /` orchestrator `cluster_endpoint` |
| `app/routes/cluster_openapi.py` | the OpenAPI of `POST /` from the settings: request headers, every failure status with `FailureBody` and its headers |
| `app/routes/read_request.py` | `read_body` (async, see below), `read_cluster_request`, `named_by_header` |
| `app/routes/health_routes.py` | `/health/live`, `/health/ready` (both return `up`; real readiness is a TODO) |
| `app/access.py` | `check_access`, `expected_credentials` (not decorated: its result holds the password) |
| `app/cluster_client.py` | `send_to_cluster`, `unreachable_error`, `was_not_sent`, `outgoing_headers`, `returned_headers` |
| `app/response_builder.py` | `build_response(cluster_response, rules, settings)` |
| `app/rules.py` | `ResponseRules` (schema validator, ignored and redacted fields) and `load_rules` |
| `app/json_file.py` | `read_json_file` (reads a JSON file from `config/`, raises the given `ConfigFileLoadError`) |
| `app/field_paths.py` | `load_field_paths`, `parse_field_path`, `remove_fields`, `remove_field` (used for ignored and redacted fields) |
| `app/schema.py` | `load_schema`, `validate_body`, `violation_at`, `every_error` |
| `app/failures/` | `codes.py` (`failure_code`), `log.py` (`record_failure`, `failure_record`, `redacted_content`), `response.py` (`failure_response`, `failure_details`, `failure_body`, `own_answer`: every answer the service writes itself), `reason_parts.py` (`reason_parts`, `shortened_field`), `handlers.py` (`refused_request_response`, `access_denied_response` (adds the `www-authenticate` challenge), `internal_error_response`, `logged_answer`: the one place that logs a failure and builds its answer) |
| `app/logger/formatters.py` | JSON + line formatters |
| `app/logger/handlers.py` | terminal / file handlers |
| `app/logger/setup.py` | `configure_logging`, `reset_logging` |
| `app/logger/decorators.py` | `log_debug`, `log_info` |
| `app/logger/quiet.py` | `QuietPathsMiddleware` (marks a request to `log.quiet_paths` in the `quiet_request` context variable), `QuietRequestFilter` (on every handler: drops its records below `log.quiet_kept_level`, uvicorn's access line included; failures stay) |
| `run_local.py` / `docker/entrypoint.py` | local run with settings in code / container run with settings from env |
| `config/response-schema.json`, `config/ignored-fields.json`, `config/redacted-fields.json` | the three runtime files (never baked into the image) |
| `helm/` | OpenShift chart: Deployment, Service, Route, ConfigMap and Secret (keys only from `config` / `secret` in values), files ConfigMap (every `helm/files/*.json`, as is), optional collector sidecar (`collector.*`). One values file per network in `helm/networks/` (`domain`, optional `image.tag` / `route.host`); `_helpers.tpl` builds the image and route host from `domain`. `values.schema.json` restricts every value; generated keys are the env vars, minus those the image owns (host, port) |
| `config/examples/` | example schema + ignored fields for every answer the manager uses; real answers, passwords replaced, are in `tests/support/cluster_samples/` |

## Mandatory coding rules (the owner enforces these strictly)

1. **Keyword-only everything**: every parameter after `*`, every call by keyword (`f(a=1)`), including library
   calls where possible. Only framework-fixed signatures stay positional (ASGI `__call__`, `logging.Filter.filter`,
   `Formatter.format`, middleware `__init__(app, ...)`, exception handlers). Tests and fixtures are exempt from the `*`.
2. **Type hints on everything**, including local variables (`x: int = ...`).
3. **Pydantic only** for data (no dataclasses). Models extend `FrozenModel`, config classes `BaseConfig`.
4. **Logging by decorator**: every function gets `@log_debug` (all arguments in, result or error out). Key steps
   also get `@log_info(inputs=(...), outputs=(...))`. Write a log call by hand only when the message needs data from
   inside the function (the failure WARNING, the `invalid_request` WARNING, the `internal_error` ERROR, and the DEBUG line of `validate_body`
   with the original schema message). **Exception:** functions whose arguments or result
   contain the cluster password are not decorated (`outgoing_headers`; `read_cluster_request` stays decorated on
   purpose, see below). Also not decorated: `lifespan` (logging
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
- **`verify=False`** to the clusters is intentional (internal certificates). Do not "fix" it.
- **No `uv.lock` in git**: the lock stores every package's index URL, and the company network installs from a
  different artifactory than pypi.org, so one lock cannot work in both. Each place resolves `pyproject.toml`
  against its own index; run `uv sync` once after cloning (pre-commit uses `uv run --frozen`).
- **Config defaults** (pydantic-settings `nested_model_default_partial_update`): a class used once has its
  defaults on its fields and its parent uses `default_factory`; a shape used several times (`FailureCode`,
  `HandlerSettings` → `FileSettings` → `FailureFileSettings`) has none, and its parent gives a full instance.
  One ENV value (`CLUSTER_CLIENT_FAILURES__REJECTED__STATUS_CODE`) keeps the other defaults.
- **Header names are `settings.headers`**: each `HeaderSettings` field names the header that carries the
  `ClusterRequest` field of the same name; `read_cluster_request` maps them and a refusal names the header
  (`loc: ["x-cluster-url"]`). Env names: `CLUSTER_CLIENT_HEADERS__*`.
- **`authorization` is required** (no request may reach a cluster without credentials).
- **Access to the cluster client** (owner's decision 2026-11-15): one header (`settings.access.header`,
  `authorization`, the standard header) with `Basic base64(username:password)` (scheme in any case, credentials compared in constant time), checked by the `require_access` dependency before the body is read. `/docs` shows it as an HTTP Basic login (`BasicAuthDocumentation`, documentation only: it checks nothing). The
  DataPower in front authenticates with the same header and passes it on; it is never sent to the cluster (the
  cluster gets its own `authorization`, built from `x-cluster-authorization`). Username and
  password have no defaults: the service does not start without them; in Helm they are required in `secret`.
  Health endpoints stay open (probes). More complex access logic only when the owner asks.
- **Response headers**: all cluster headers are returned except `recomputed_response_headers` (content-length,
  content-encoding, transfer-encoding, connection). uvicorn's own `date`/`server` headers are off.
- **Ignored field paths** use the same format as the `field` of a rejection: `$.a.b`, `[*]` for every list item
  (`$[*].shards_placement`). Indexes like `[0]` and paths ending in `[*]` are rejected at startup.
- **Failure file** (`logs/failures.log`, logger `cluster_client.failures`): one JSON line per failed request,
  including the cluster response without the redacted fields (`validation.redacted_fields_path`: the passwords
  Redis returns in bdb and crdb answers). DEBUG logs everything, on purpose.
- **Pass-through headers** (`cluster-state-id`, `x-task-id`, `x-result-ttl`) are sent as they are; the
  client's own authorization and content-type always win over them, and OpenTelemetry sets `traceparent`.
- **Tracing** is OpenTelemetry. Find a failure by the `trace_id` of the `traceresponse` header (the manager's own
  trace id). `LoggingInstrumentor` only adds `otelTraceID`/`otelSpanID` to records.
- **Logs and traces to Elastic** (owner's decision 2026-11-15): the service never talks to Elastic. Helm
  `collector.enabled` adds an OpenTelemetry Collector sidecar (`configmap-collector.yaml`, `secret-collector.yaml`):
  the service writes every line at `collector.logLevel` (default DEBUG, passwords included) as JSON to
  `logs/app.log` (shared `emptyDir`) and sends spans to `127.0.0.1:4318`; the collector reads both and sends them
  to Elasticsearch with its own username/password. Logs still never leave through the service's OTLP
  (`enable_log_auto_instrumentation=False`). The owner will remove secrets before they are logged when needed.
- **Quiet paths** (owner's decision 2026-11-15): requests to `log.quiet_paths` (default the two probes) write no
  log line below `log.quiet_kept_level` (WARNING) in any handler, so their failures still reach the failure file,
  and get no span (`excluded_urls` of `FastAPIInstrumentor`, anchored to the exact path), so the probes do not
  flood the terminal and Elastic.
- `RequestsInstrumentor` patches `requests` in the whole process: a test client using `requests` in the same
  process gets its `traceparent` overwritten.
- **Timeouts**: `requests` applies its timeout per stage, so `connect_timeout_seconds` + `timeout_seconds` is kept
  below the manager's own timeout (35 seconds, contract C15).
- The error `reason` from `requests` is long; the owner chose to keep it as is.
- **DEBUG logs the cluster password** (`read_cluster_request` receives all headers). The owner chose this; do not
  "fix" it. The owner must always have one place with the full error and the whole call: the DEBUG file log
  (`CLUSTER_CLIENT_LOG__FILE__ENABLED=true`, off by default). Never clean a secret without keeping it there.
- **Every body the service writes itself passes the firewall schema** (`response-schema-depth.json` in
  redis-enterprise-services, copied to `tests/support/firewall-response-schema.json`): `{"error", "rule",
  "field", "reason"}`, `reason` a list of parts of up to `part_length` (512), at most `max_parts` (500), the last
  one then saying how many characters were not sent; `field` over 512 is cut from the start, `...` included.
- **The rejection `reason`** (replaces "keeps the blocked value… even a password", owner's decision 2026-11-13,
  because of the 512-character limit of DataPower): only the `redacted_fields` are removed, from a copy of the
  body; everything else, even an unknown password, goes out in full. `rule` and `field` always come from the
  real failure; `reason` comes from the copy's failure at the same path, else it is `redacted_reason`. The
  original `error.message`, with the password, stays in the DEBUG log (a hand-written line in `validate_body`).
  `violation_at` looks at every failure of the copy, `anyOf` context included, without `best_match` descending
  again. No generic fallback: no `except Exception` around building the explanation. `FailureSettings` refuses
  texts that could not pass the firewall (unknown placeholders, prefix or unsent message too long).
- **The failure file always has the whole error, never cut** (owner's decision 2026-11-14): every failure the
  service answers itself (`invalid_request` and `internal_error` included) is written there with the full
  `reason` and `field`, at WARNING/ERROR, not only at DEBUG. Only the answer is cut to the firewall limits.
  `internal_error` sends and logs the error and its traceback.
- **`helm/files/` copies** `config/redacted-fields.json` and `config/ignored-fields.json` (Helm reads only inside
  the chart); `tests/unit/test_helm_files.py` fails when a copy differs. `response-schema.json` differs on purpose:
  locally a placeholder, in Helm the firewall schema. The collector keeps its read offset of `app.log` in the
  `collector-state` `emptyDir` (`file_storage`), so a collector restart resends nothing.
- **One schema, one set of field files per service.** More technologies later: first change the schema, change
  the logic only if there is no other choice. Non-JSON answers stay rejected, Redis-specific defaults stay.

## Tests

- **Unit tests only, on the main logic.** No integration or E2E tests, no tests of code that only connects parts, no coverage gate.
- **Test only this project's logic. Never test library behaviour** (Pydantic validation, env parsing, logging
  propagation, SecretStr masking…). Ask: "if this fails, is the bug in our code?" If not, don't write it.
- The cluster is faked by replacing `app.cluster_client.requests.request` (`tests/support/fake_cluster_api.py`,
  `fake_cluster` fixture). One assertion/behaviour per test.
- Run: `pytest`.

## Working with the owner

- A question ("why…?", "what is…?") is **not** a request to change code. Answer, propose, wait for "yes".
- **Never commit** unless explicitly asked. Conventional Commits; single branch `main`.
- When code changes make `docs/diagrams/` stale, update the diagrams in the same task (edit cells in place, keep the
  layout, render to check); do not touch them for changes they do not show.
- Keep answers short; the owner writes in Hebrew.

## Open items (do not implement without the owner)

- `/health/ready` should check something real.
- Whether cluster-client should hold a list of known clusters/credentials: `docs/proposals/cluster-health-check.md`.
