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
2. `read_cluster_request` (`app/routes/read_request.py`) turns the incoming headers + body into a
   `ClusterRequest`, including the configured pass-through headers. Missing/invalid header → HTTP 400 with
   `x-edge-error: invalid_request` (from config). Nothing is sent to the cluster.
3. `send_to_cluster` (`app/cluster_client.py`) calls the cluster with `requests`; `RequestsInstrumentor` adds
   `traceparent`. Any `RequestException` →
   `ConnectionFailedError` when the request surely did not leave (`requests` wraps it in `MaxRetryError`:
   refused, DNS, connect timeout), else `NoResponseError` (read timeout, connection cut, any TLS error: it can
   happen after the cluster got the request).
4. `build_response` (`app/response_builder.py`):
   - empty body (e.g. 204) → returned as is;
   - decode JSON (not JSON → `ResponseRejectedError`, field `$`);
   - `remove_fields` (`app/field_paths.py`) removes the configured ignored field paths ("function X");
   - `validate_body` (`app/schema.py`) checks the JSON Schema (violation → `ResponseRejectedError` with the
     failing field, e.g. `$.uid`);
   - if X removed nothing → the **original** response object is returned; else the body is re-encoded.
5. On any `RequestFailedError`: `record_failure` writes one JSON line to the failure log file (redacted
   fields left out of the cluster response), then `failure_response` builds the answer with `x-edge-error`,
   and on a rejection `x-edge-cluster-status` (`app/failures/`). Anything else the service answers itself goes
   through the handlers of `app/failures/handlers.py`, so every such answer has `x-edge-error`: `HTTPException`
   (bad headers, wrong path, wrong method) → `invalid_request`; any other exception → `internal_error`.
6. The route returns status + headers + body; OpenTelemetry adds `traceresponse`.

Diagrams of exactly this flow: `docs/diagrams/flow.drawio` (activity) and `docs/diagrams/class-diagram.drawio`.

## File map

| File | Contents |
|---|---|
| `app/main.py` | `create_app(settings)` (factory) and `lifespan` (startup: configure logging, start telemetry, load schema, ignored and redacted fields into `app.state`) |
| `app/server.py` | `serve()` → `uvicorn.run` |
| `app/telemetry.py` | `build_tracer_provider`, `start_telemetry`: OpenTelemetry for `requests` and logs. `FastAPIInstrumentor` is applied in `create_app` |
| `app/config/` | **every** setting, one file per section: `base.py` (`FrozenModel`, `EnvironmentSettings`, `TEXT_ENCODING`, field types), `server.py`, `headers.py`, `forwarding.py`, `validation.py` (schema, ignored and redacted field files), `failures.py`, `logging.py` (`HandlerSettings` → console / file → failure file), `telemetry.py`, `settings.py` (root `Settings`, env prefix `CLUSTER_CLIENT_`, nested `__`; `NoEnvFileSettings` ignores `.env`) |
| `app/models.py` | `ClusterRequest`, `ClusterResponse`, `FailureBody`, `RequestFailure`, `HttpMethod`, `HealthStatus` |
| `app/errors.py` | `ClusterClientError` → `ConfigFileLoadError` (→ `SchemaLoadError`, `FieldPathsLoadError`), `RequestFailedError` → `ClusterUnreachableError` (→ `ConnectionFailedError`, `NoResponseError`), `ResponseRejectedError` |
| `app/routes/cluster_routes.py` | `POST /` orchestrator |
| `app/routes/read_request.py` | `read_body` (async, see below) and `read_cluster_request` |
| `app/routes/health_routes.py` | `/health/live`, `/health/ready` (both return `up`; real readiness is a TODO) |
| `app/cluster_client.py` | `send_to_cluster`, `unreachable_error`, `was_not_sent`, `outgoing_headers`, `returned_headers` |
| `app/response_builder.py` | `build_response`, `decode_body`, `encode_body` |
| `app/field_paths.py` | `load_field_paths`, `parse_field_path`, `remove_fields`, `remove_field` (used for ignored and redacted fields) |
| `app/schema.py` | `load_schema`, `read_schema_file`, `validate_body` |
| `app/failures/` | `codes.py` (`failure_code`), `log.py` (`record_failure`, `failure_record`, `redacted_content`), `response.py` (`failure_response`), `handlers.py` (`refused_request_response`, `internal_error_response`) |
| `app/logger/formatters.py` | JSON + line formatters |
| `app/logger/handlers.py` | terminal / file handlers |
| `app/logger/setup.py` | `configure_logging`, `reset_logging` |
| `app/logger/decorators.py` | `log_debug`, `log_info` |
| `run_local.py` / `docker/entrypoint.py` | local run with settings in code / container run with settings from env |
| `config/response-schema.json`, `config/ignored-fields.json`, `config/redacted-fields.json` | the three runtime files (never baked into the image) |
| `helm/` | OpenShift chart: Deployment, Service, Route, ConfigMap and Secret (keys only from `config` / `secret` in values), files ConfigMap. `values.schema.json` restricts every value; generated keys are the env vars, minus those the image owns (host, port) |
| `config/examples/` | example schema + ignored fields for every answer the manager uses; real answers, passwords replaced, are in `tests/support/cluster_samples/` |

## Mandatory coding rules (the owner enforces these strictly)

1. **Keyword-only everything**: every parameter after `*`, every call by keyword (`f(a=1)`), including library
   calls where possible. Only framework-fixed signatures stay positional (ASGI `__call__`, `logging.Filter.filter`,
   `Formatter.format`, middleware `__init__(app, ...)`, exception handlers). Tests and fixtures are exempt from the `*`.
2. **Type hints on everything**, including local variables (`x: int = ...`).
3. **Pydantic only** for data (no dataclasses). Models extend `FrozenModel`.
4. **Logging by decorator**: every function gets `@log_debug` (all arguments in, result or error out). Key steps
   also get `@log_info(inputs=(...), outputs=(...))`. Write a log call by hand only when the message needs data from
   inside the function (only the failure WARNING does this). **Exception:** functions whose arguments or result
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
- **Header names → model via aliases**: `ClusterRequest` fields use `validation_alias` read from `HeaderSettings`
  at import time (`HEADER_NAMES` in `models.py`). So header names come from ENV/`.env` only, not from the
  `Settings` passed to `create_app`.
- **`authorization` is required** (no request may reach a cluster without credentials).
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
  trace id). Spans leave only when `telemetry.export_enabled` is on; default off. `LoggingInstrumentor` only adds
  `otelTraceID`/`otelSpanID` to records: `enable_log_auto_instrumentation=False` keeps logs, with their passwords,
  from leaving through OTLP.
- `RequestsInstrumentor` patches `requests` in the whole process: a test client using `requests` in the same
  process gets its `traceparent` overwritten.
- **Timeouts**: `requests` applies its timeout per stage, so `connect_timeout_seconds` + `timeout_seconds` is kept
  below the manager's own timeout (35 seconds, contract C15).
- The error `reason` from `requests` is long; the owner chose to keep it as is.
- **DEBUG logs the cluster password** (`read_cluster_request` receives all headers). The owner chose this; do not
  "fix" it. The owner must always have one place with the full error and the whole call: the DEBUG file log
  (`CLUSTER_CLIENT_LOG__FILE__ENABLED=true`, off by default). Never clean a secret without keeping it there.
- **The rejection `reason` keeps the blocked value**, as jsonschema wrote it, even a password, in the answer to
  the manager and in the failure file. The owner uses it to see the problem without going to the other network.
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
- Do not redraw diagrams unless asked; if code changes make them stale, say so.
- Keep answers short; the owner writes in Hebrew.

## Open items (do not implement without the owner)

- `/health/ready` should check something real.
- Whether cluster-client should hold a list of known clusters/credentials: `docs/proposals/cluster-health-check.md`.
- Final shape of the rejection body returned to the manager.
