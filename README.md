# cluster-client

Runs inside each network. The manager sends it a request; it calls the Redis Enterprise REST API of the
cluster named in the request, checks the answer against a JSON schema, and returns it.

## Installation

```bash
uv venv -p 3.14
uv pip install -e ".[dev]"
pre-commit install
cp .env.example .env
```

## Run

```bash
python run_local.py
```

The app is built by `app.main.create_app(settings)`. Each environment passes its own `Settings`:

| Environment | Entry | Settings come from |
|---|---|---|
| Local | `run_local.py` | written in the file |
| Tests | `tests/conftest.py` | `tests/support/app_settings.py` |
| Docker / Helm | `docker/entrypoint.py` | `CLUSTER_CLIENT_*` env vars (all listed in `.env.example`) |

## Usage

`POST /` with the call to make in headers (names set by `CLUSTER_CLIENT_HEADERS__*`):

```bash
curl -X POST http://127.0.0.1:8000/ \
  -H "x-cluster-method: GET" \
  -H "x-cluster-url: https://cluster.example:9443/v1/bdbs" \
  -H "x-cluster-authorization: Basic <credentials>"
```

The request body, if any, is sent to the cluster as is. An incoming `traceparent` is continued to the
cluster and returned in the response. The headers in `CLUSTER_CLIENT_FORWARDING__PASSED_THROUGH_REQUEST_HEADERS`
(`cluster-state-id`, `x-task-id`, `x-result-ttl`) are sent on to the cluster as they are.

| Case | Status | Body |
|---|---|---|
| Answer matches the schema | the cluster's | the cluster's, unchanged (with its headers) |
| Answer is not JSON or breaks the schema | 502 | `{"error": "response_rejected", "reason", "field"}` |
| Cluster cannot be reached | 502 | `{"error": "cluster_unreachable", "reason"}` |
| A required header is missing or invalid | 400 | the validation errors |

Status codes and error codes are set by `CLUSTER_CLIENT_FAILURES__*`.

Two files are read at startup; replace them without touching the code or the image:

| File | Setting | Content |
|---|---|---|
| `config/response-schema.json` | `CLUSTER_CLIENT_VALIDATION__SCHEMA_PATH` | the JSON Schema every answer must match |
| `config/ignored-fields.json` | `CLUSTER_CLIENT_VALIDATION__IGNORED_FIELDS_PATH` | field paths removed before the check |

Ignored fields use the same format as `field` in a rejection, with `[*]` for every item of a list:

```json
["$[*].shards_placement", "$.endpoints[*].internal_id"]
```

When a field is removed, the answer is re-encoded; otherwise it is returned byte for byte.

Health probes: `GET /health/live`, `GET /health/ready`.

## Logging

| Output | Default | Setting |
|---|---|---|
| Terminal (stdout) | on, INFO, `line` | `CLUSTER_CLIENT_LOG__CONSOLE__*` |
| Main file `logs/app.log` | off, DEBUG, `json` | `CLUSTER_CLIENT_LOG__FILE__*` |
| Failure file `logs/failures.log` | on, one JSON line per failed request | `CLUSTER_CLIENT_LOG__FAILURE_FILE__*` |

Every line carries the `trace_id`; find a failure by the trace id of its response:

```bash
grep '"trace_id": "<trace id>"' logs/failures.log
```

In code, logging is done by decorators:

```python
from app.logger import log_debug, log_info


@log_info(inputs=("request.method", "request.url"), outputs=("status_code",))
@log_debug
def send_to_cluster(*, request: ClusterRequest, ...) -> ClusterResponse: ...
```

- `@log_debug` (every function): DEBUG lines with all arguments, and the return value or the error.
- `@log_info(inputs=..., outputs=...)` (key steps): one INFO line with the chosen values and the duration.

## Tests

```bash
pytest                 # all tiers
pytest -m unit
pytest -m integration
pytest -m e2e          # real servers on free ports
pytest --cov=app
```

## Lint

```bash
ruff check . && ruff format .
```

## Docker

```bash
docker build -f docker/Dockerfile -t cluster-client:0.1.0 .
docker run --rm -p 8000:8000 --read-only -v /app/logs -v "$PWD/config:/etc/cluster-client:ro" cluster-client:0.1.0
```

## Helm

```bash
helm lint helm
helm upgrade --install cluster-client helm \
  --set image.repository=<registry>/cluster-client \
  --set image.tag=0.1.0 \
  --set-file responseSchema=config/response-schema.json \
  --set-file ignoredFields=config/ignored-fields.json
```

Plain settings go under `config:` in `values.yaml`; credentials go in a Secret listed in `envFromSecrets`.

## Diagrams

`docs/diagrams/flow.drawio` (request flow) and `docs/diagrams/class-diagram.drawio` (classes in that flow).
