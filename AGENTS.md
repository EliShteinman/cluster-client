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

1. `TraceMiddleware` (`app/logger/tracing.py`) continues the manager's `traceparent` (or starts a trace).
2. `read_cluster_request` (`app/routes/read_request.py`) turns the incoming headers + body into a
   `ClusterRequest`, including the configured pass-through headers. Missing/invalid header → HTTP 400 with
   `x-edge-error: invalid_request` (from config). Nothing is sent to the cluster.
3. `send_to_cluster` (`app/cluster_client.py`) calls the cluster with `requests`. Any `RequestException` →
   `ConnectionFailedError` when the request surely did not leave (`requests` wraps it in `MaxRetryError`:
   refused, DNS, connect timeout), else `NoResponseError` (read timeout, connection cut after sending).
4. `build_response` (`app/response_builder.py`):
   - empty body (e.g. 204) → returned as is;
   - decode JSON (not JSON → `ResponseRejectedError`, field `$`);
   - `remove_fields` (`app/field_paths.py`) removes the configured ignored field paths ("function X");
   - `validate_body` (`app/schema.py`) checks the JSON Schema (violation → `ResponseRejectedError` with the
     failing field, e.g. `$.uid`);
   - if X removed nothing → the **original** response object is returned; else the body is re-encoded.
5. On any `RequestFailedError`: `record_failure` writes one JSON line to the failure log file (redacted
   fields left out of the cluster response), then `failure_response` builds the answer with `x-edge-error`,
   and on a rejection `x-edge-cluster-status` (`app/failures.py`).
6. The route returns status + headers + body; the middleware adds `traceparent`.

Diagrams of exactly this flow: `docs/diagrams/flow.drawio` (activity) and `docs/diagrams/class-diagram.drawio`.

## File map

| File | Contents |
|---|---|
| `app/main.py` | `create_app(settings)` (factory) and `lifespan` (startup: configure logging, load schema, ignored and redacted fields into `app.state`) |
| `app/server.py` | `serve()` → `uvicorn.run` |
| `app/config/settings.py` | **every** setting (Pydantic Settings, env prefix `CLUSTER_CLIENT_`, nested `__`), `TEXT_ENCODING`, `FrozenModel` |
| `app/models.py` | `ClusterRequest`, `ClusterResponse`, `FailureBody`, `RequestFailure`, `HttpMethod`, `HealthStatus` |
| `app/errors.py` | `ClusterClientError` → `SchemaLoadError`, `FieldPathsLoadError`, `RequestFailedError` → `ClusterUnreachableError` (→ `ConnectionFailedError`, `NoResponseError`), `ResponseRejectedError` |
| `app/routes/__init__.py` | creates `cluster_router` and `health_router`; route files import them |
| `app/routes/cluster_routes.py` | `POST /` orchestrator |
| `app/routes/read_request.py` | `read_body` (async, see below) and `read_cluster_request` |
| `app/routes/health_routes.py` | `/health/live`, `/health/ready` (both return `up`; real readiness is a TODO) |
| `app/cluster_client.py` | `send_to_cluster`, `unreachable_error`, `was_not_sent`, `outgoing_headers`, `returned_headers` |
| `app/response_builder.py` | `build_response`, `decode_body`, `encode_body` |
| `app/field_paths.py` | `load_field_paths`, `parse_field_path`, `remove_fields`, `remove_field` (used for ignored and redacted fields) |
| `app/schema.py` | `load_schema`, `read_schema_file`, `validate_body` |
| `app/failures.py` | `failure_code`, `record_failure`, `failure_record`, `redacted_content`, `failure_response` |
| `app/logger/setup.py` | handlers (terminal / file / failure file), JSON + line formatters, `configure_logging` |
| `app/logger/decorators.py` | `log_debug`, `log_info` |
| `app/logger/tracing.py` | W3C traceparent parse/format, context var, log filter, `TraceMiddleware` |
| `run_local.py` / `docker/entrypoint.py` | local run with settings in code / container run with settings from env |
| `config/response-schema.json`, `config/ignored-fields.json`, `config/redacted-fields.json` | the three runtime files (never baked into the image) |

## Mandatory coding rules (the owner enforces these strictly)

1. **Keyword-only everything**: every parameter after `*`, every call by keyword (`f(a=1)`), including library
   calls where possible. Only framework-fixed signatures stay positional (ASGI `__call__`, `logging.Filter.filter`,
   `Formatter.format`, middleware `__init__(app, ...)`).
2. **Type hints on everything**, including local variables (`x: int = ...`).
3. **Pydantic only** for data (no dataclasses). Models extend `FrozenModel`.
4. **Logging by decorator**: every function gets `@log_debug` (all arguments in, result or error out). Key steps
   also get `@log_info(inputs=(...), outputs=(...))`. Write a log call by hand only when the message needs data from
   inside the function (only the failure WARNING does this). **Exception:** functions whose arguments or result
   contain the cluster password (`outgoing_headers`) are not decorated.
5. **Config is the single source** of every name the code expects (header names, status codes, error codes, paths,
   logger names). No string constants in code for these. Route paths in decorators are allowed.
6. **Simplicity over patterns.** Functions, not classes, unless a library requires a class. No speculative
   extension points, no protocols/interfaces with one implementation, no extra layers. Few files per concept.
7. Ruff must pass (`ruff check . && ruff format .`), line length 110.

## Decisions that look odd but are deliberate

- **Sync code + `requests`**: the owner chose sync for readability. FastAPI runs `def` routes in a thread pool.
  Only three things stay `async` because the libraries demand it: `lifespan`, `TraceMiddleware`, and `read_body`
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
  including the cluster response without the redacted fields (`config/redacted-fields.json`: the passwords
  Redis returns in bdb and crdb answers). DEBUG logs everything, on purpose.
- **Pass-through headers** (`cluster-state-id`, `x-task-id`, `x-result-ttl`) are sent as they are; the
  client's own authorization, content-type and traceparent always win over them. Find it by the `trace_id` the manager got back in `traceparent`.
- The error `reason` from `requests` is long; the owner chose to keep it as is.

## Tests

- Tiers by folder: `tests/unit`, `tests/integration`, `tests/e2e` (markers added automatically).
- **Test only this project's logic. Never test library behaviour** (Pydantic validation, env parsing, logging
  propagation, SecretStr masking…). Ask: "if this fails, is the bug in our code?" If not, don't write it.
- The cluster is faked by replacing `app.cluster_client.requests.request` (`tests/support/fake_cluster_api.py`,
  `fake_cluster` fixture). One assertion/behaviour per test.
- Run: `pytest`, `pytest -m unit`, `pytest --cov=app` (gate 80%).

## Working with the owner

- A question ("why…?", "what is…?") is **not** a request to change code. Answer, propose, wait for "yes".
- **Never commit** unless explicitly asked. Conventional Commits; branch `feature/app-scaffolding`.
- Do not redraw diagrams unless asked; if code changes make them stale, say so.
- Keep answers short; the owner writes in Hebrew.

## Open items (do not implement without the owner)

- `/health/ready` should check something real.
- Whether cluster-client should hold a list of known clusters/credentials: `docs/proposals/cluster-health-check.md`.
- Final shape of the rejection body returned to the manager.
