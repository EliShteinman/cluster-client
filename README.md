# cluster-client

Runs inside each network. The manager sends it a request; it calls the Redis Enterprise REST API of the
cluster named in the request, checks the answer against a JSON schema, and returns it.

## Installation

```bash
uv sync
uv run pre-commit install
cp .env.example .env
```

## Run

```bash
python run_local.py
```

`run_local.py` sets local credentials (`manager` / `local-password`). Everywhere else the service does not start
without `CLUSTER_CLIENT_ACCESS__USERNAME` and `CLUSTER_CLIENT_ACCESS__PASSWORD` (no defaults).

The app is built by `app.main.create_app(settings)`. Each environment passes its own `Settings`:

| Environment | Entry | Settings come from |
|---|---|---|
| Local | `run_local.py` | written in the file |
| Docker / Helm | `docker/entrypoint.py` | `CLUSTER_CLIENT_*` env vars (see Configuration) |

## Usage

`POST /` with the manager's own credentials and the call to make in headers (names set by
`CLUSTER_CLIENT_ACCESS__HEADER` and `CLUSTER_CLIENT_HEADERS__*`):

```bash
curl -X POST http://127.0.0.1:8000/ \
  -H "authorization: Basic $(printf 'manager:<password>' | base64)" \
  -H "x-cluster-method: GET" \
  -H "x-cluster-url: https://cluster.example:9443/v1/bdbs" \
  -H "x-cluster-authorization: Basic <credentials>"
```

`Authorization` is `Basic base64(username:password)`; the scheme may be in any case. In `/docs`, click
**Authorize** and enter the same username and password to try `POST /`.

The request body, if any, is sent to the cluster as is. An incoming `traceparent` is continued to the
cluster, and the response carries `traceresponse`. The headers in `CLUSTER_CLIENT_FORWARDING__PASSED_THROUGH_REQUEST_HEADERS`
(`cluster-state-id`, `x-task-id`, `x-result-ttl`) are sent on to the cluster as they are.

| Case | Status | `x-edge-error` | Body |
|---|---|---|---|
| Answer matches the schema | the cluster's | none | the cluster's, unchanged (with its headers) |
| Answer is not JSON or breaks the schema | 502 | `response_rejected` | `{"error", "rule", "field", "reason"}` |
| Request surely did not reach the cluster (refused, DNS, connect timeout) | 502 | `connection_failed` | `{"error", "reason"}` |
| Request may have been sent, no full answer (read timeout, connection cut, TLS error) | 504 | `timeout` | `{"error", "reason"}` |
| `Authorization` is missing or wrong (nothing is sent to the cluster) | 401 | `unauthorized` | `{"error", "reason"}`, with `www-authenticate: Basic realm="cluster-client"` |
| A required header is missing or invalid | 400 | `invalid_request` | `{"error", "reason"}` (the validation errors) |
| Wrong path or method on the cluster client | 404, 405 | `invalid_request` | `{"error", "reason"}` |
| Unexpected error inside the cluster client | 500 | `internal_error` | `{"error", "reason"}` (the error and its traceback) |

`x-edge-error` is on every answer the cluster client made itself, and never on a cluster answer. A
`response_rejected` answer also carries the cluster's status in `x-edge-cluster-status`. Status codes, error
codes and header names are set by `CLUSTER_CLIENT_FAILURES__*`.

Every body the cluster client writes itself passes the firewall's response schema:

```json
{"error": "response_rejected", "rule": "anyOf", "field": "$.shard_list", "reason": ["...", "..."]}
```

- `rule`: the JSON Schema keyword that failed (`not_json` when the answer is not JSON); rejections only.
- `field`: the failing field; longer than 256 characters, it is cut from the start and begins with `...`.
- `reason`: the whole explanation in parts of up to 256 characters; joined, they are the full text. Above 500
  parts, the last part says how many characters were not sent.
- The explanation is built after removing the redacted fields, so no listed password reaches it; a failure in a
  redacted field itself is explained without its value. The original explanation is in the DEBUG log.

Three files are read at startup; replace them without touching the code or the image:

| File | Setting | Content |
|---|---|---|
| `helm/files/response-schema.json` | `CLUSTER_CLIENT_VALIDATION__SCHEMA_PATH` | the JSON Schema every answer must match |
| `helm/files/ignored-fields.json` | `CLUSTER_CLIENT_VALIDATION__IGNORED_FIELDS_PATH` | field paths removed before the check |
| `helm/files/redacted-fields.json` | `CLUSTER_CLIENT_VALIDATION__REDACTED_FIELDS_PATH` | field paths left out of the failure log and of a rejection's explanation (passwords) |

Ignored and redacted fields use the same format as `field` in a rejection, with `[*]` for every item of a list:

```json
["$[*].shards_placement", "$.endpoints[*].internal_id"]
```

When a field is removed, the answer is re-encoded; otherwise it is returned byte for byte.

### Example configuration

`config/examples/` holds a schema and ignored fields for every Redis Enterprise answer the manager uses (bdb,
redis_acl, role, user, crdb, crdb task, action, cluster, stats, errors). The schema forbids passwords and
certificates; the ignored fields remove them first, so the answer passes without them. Run it:

```bash
CLUSTER_CLIENT_VALIDATION__SCHEMA_PATH=config/examples/response-schema.json \
CLUSTER_CLIENT_VALIDATION__IGNORED_FIELDS_PATH=config/examples/ignored-fields.json python docker/entrypoint.py
```

Real cluster answers, passwords replaced, are kept in `tests/support/cluster_samples/`.

Health probes: `GET /health/live`, `GET /health/ready`.

The OpenAPI description of `POST /` (request headers, every failure status with its body and headers, from the
settings in use) is served at `/openapi.json` and `/docs`.

## Configuration

Every setting is a `CLUSTER_CLIENT_*` env var. Only `CLUSTER_CLIENT_ACCESS__USERNAME` and
`CLUSTER_CLIENT_ACCESS__PASSWORD` are required; set any other only to change its default. The usual ones are in
`.env.example`. In the image, `SERVER__HOST`, `SERVER__PORT`, `VALIDATION__*_PATH` and `LOG__*__PATH` are set
already. Lists are JSON (`["a", "b"]`).

| Variable | Default |
|---|---|
| `CLUSTER_CLIENT_SERVER__HOST` | `127.0.0.1` |
| `CLUSTER_CLIENT_SERVER__PORT` | `8000` |
| `CLUSTER_CLIENT_SERVER__SERVER_HEADER` | `false` |
| `CLUSTER_CLIENT_SERVER__DATE_HEADER` | `false` |
| `CLUSTER_CLIENT_APPLICATION__TITLE` | `cluster-client` |
| `CLUSTER_CLIENT_ACCESS__HEADER` | `authorization` |
| `CLUSTER_CLIENT_ACCESS__SCHEME` | `Basic` |
| `CLUSTER_CLIENT_ACCESS__USERNAME` | **required** |
| `CLUSTER_CLIENT_ACCESS__PASSWORD` | **required** |
| `CLUSTER_CLIENT_ACCESS__CHALLENGE_HEADER` | `www-authenticate` |
| `CLUSTER_CLIENT_ACCESS__REALM` | `cluster-client` |
| `CLUSTER_CLIENT_HEADERS__METHOD` | `x-cluster-method` |
| `CLUSTER_CLIENT_HEADERS__URL` | `x-cluster-url` |
| `CLUSTER_CLIENT_HEADERS__AUTHORIZATION` | `x-cluster-authorization` |
| `CLUSTER_CLIENT_HEADERS__CONTENT_TYPE` | `content-type` |
| `CLUSTER_CLIENT_VALIDATION__SCHEMA_PATH` | `helm/files/response-schema.json` |
| `CLUSTER_CLIENT_VALIDATION__IGNORED_FIELDS_PATH` | `helm/files/ignored-fields.json` |
| `CLUSTER_CLIENT_VALIDATION__REDACTED_FIELDS_PATH` | `helm/files/redacted-fields.json` |
| `CLUSTER_CLIENT_FORWARDING__CONNECT_TIMEOUT_SECONDS` | `5.0` |
| `CLUSTER_CLIENT_FORWARDING__TIMEOUT_SECONDS` | `28.0` |
| `CLUSTER_CLIENT_FORWARDING__AUTHORIZATION_HEADER` | `authorization` |
| `CLUSTER_CLIENT_FORWARDING__CONTENT_TYPE_HEADER` | `content-type` |
| `CLUSTER_CLIENT_FORWARDING__PASSED_THROUGH_REQUEST_HEADERS` | `["cluster-state-id", "x-result-ttl", "x-task-id"]` |
| `CLUSTER_CLIENT_FORWARDING__RECOMPUTED_RESPONSE_HEADERS` | `["connection", "content-encoding", "content-length", "transfer-encoding"]` |
| `CLUSTER_CLIENT_FAILURES__INVALID_REQUEST__STATUS_CODE` | `400` |
| `CLUSTER_CLIENT_FAILURES__INVALID_REQUEST__ERROR_CODE` | `invalid_request` |
| `CLUSTER_CLIENT_FAILURES__UNAUTHORIZED__STATUS_CODE` | `401` |
| `CLUSTER_CLIENT_FAILURES__UNAUTHORIZED__ERROR_CODE` | `unauthorized` |
| `CLUSTER_CLIENT_FAILURES__REJECTED__STATUS_CODE` | `502` |
| `CLUSTER_CLIENT_FAILURES__REJECTED__ERROR_CODE` | `response_rejected` |
| `CLUSTER_CLIENT_FAILURES__CONNECTION_FAILED__STATUS_CODE` | `502` |
| `CLUSTER_CLIENT_FAILURES__CONNECTION_FAILED__ERROR_CODE` | `connection_failed` |
| `CLUSTER_CLIENT_FAILURES__NO_RESPONSE__STATUS_CODE` | `504` |
| `CLUSTER_CLIENT_FAILURES__NO_RESPONSE__ERROR_CODE` | `timeout` |
| `CLUSTER_CLIENT_FAILURES__INTERNAL_ERROR__STATUS_CODE` | `500` |
| `CLUSTER_CLIENT_FAILURES__INTERNAL_ERROR__ERROR_CODE` | `internal_error` |
| `CLUSTER_CLIENT_FAILURES__ERROR_HEADER` | `x-edge-error` |
| `CLUSTER_CLIENT_FAILURES__CLUSTER_STATUS_HEADER` | `x-edge-cluster-status` |
| `CLUSTER_CLIENT_FAILURES__CONTENT_TYPE` | `application/json` |
| `CLUSTER_CLIENT_FAILURES__PART_LENGTH` | `256` |
| `CLUSTER_CLIENT_FAILURES__MAX_PARTS` | `500` |
| `CLUSTER_CLIENT_FAILURES__SHORTENED_FIELD_PREFIX` | `...` |
| `CLUSTER_CLIENT_FAILURES__UNSENT_CHARACTERS_MESSAGE` | `{count} more characters were not sent` |
| `CLUSTER_CLIENT_FAILURES__NOT_JSON_RULE` | `not_json` |
| `CLUSTER_CLIENT_FAILURES__NOT_JSON_REASON` | `the response body is not JSON: {error}` |
| `CLUSTER_CLIENT_FAILURES__REDACTED_REASON` | `the failing value is a redacted field` |
| `CLUSTER_CLIENT_LOG__LEVEL` | `DEBUG` |
| `CLUSTER_CLIENT_LOG__QUIET_PATHS` | `["/health/live", "/health/ready"]` |
| `CLUSTER_CLIENT_LOG__QUIET_KEPT_LEVEL` | `WARNING` |
| `CLUSTER_CLIENT_LOG__CONSOLE__ENABLED` | `true` |
| `CLUSTER_CLIENT_LOG__CONSOLE__LEVEL` | `INFO` |
| `CLUSTER_CLIENT_LOG__CONSOLE__FORMAT` | `line` |
| `CLUSTER_CLIENT_LOG__FILE__ENABLED` | `false` |
| `CLUSTER_CLIENT_LOG__FILE__LEVEL` | `DEBUG` |
| `CLUSTER_CLIENT_LOG__FILE__FORMAT` | `json` |
| `CLUSTER_CLIENT_LOG__FILE__PATH` | `logs/app.log` |
| `CLUSTER_CLIENT_LOG__FILE__MAX_BYTES` | `10485760` |
| `CLUSTER_CLIENT_LOG__FILE__BACKUP_COUNT` | `5` |
| `CLUSTER_CLIENT_LOG__FAILURE_FILE__ENABLED` | `true` |
| `CLUSTER_CLIENT_LOG__FAILURE_FILE__LEVEL` | `WARNING` |
| `CLUSTER_CLIENT_LOG__FAILURE_FILE__FORMAT` | `json` |
| `CLUSTER_CLIENT_LOG__FAILURE_FILE__PATH` | `logs/failures.log` |
| `CLUSTER_CLIENT_LOG__FAILURE_FILE__MAX_BYTES` | `10485760` |
| `CLUSTER_CLIENT_LOG__FAILURE_FILE__BACKUP_COUNT` | `5` |
| `CLUSTER_CLIENT_LOG__FAILURE_FILE__LOGGER_NAME` | `cluster_client.failures` |
| `CLUSTER_CLIENT_LOG__FORMATTING__LINE_PATTERN` | `%(asctime)s \| %(levelname)-8s \| %(name)s \| trace_id=%(otelTraceID)s \| %(message)s` |
| `CLUSTER_CLIENT_LOG__FORMATTING__DATE_FORMAT` | `%Y-%m-%dT%H:%M:%S%z` |
| `CLUSTER_CLIENT_TELEMETRY__SERVICE_NAME` | `cluster-client` |
| `CLUSTER_CLIENT_TELEMETRY__EXPORT_ENABLED` | `false` |
| `CLUSTER_CLIENT_TELEMETRY__OTLP_ENDPOINT` | `http://localhost:4318` |
| `CLUSTER_CLIENT_TELEMETRY__TRACES_PATH` | `/v1/traces` |

## Logging

| Output | Default | Setting |
|---|---|---|
| Terminal (stdout) | on, INFO, `line` | `CLUSTER_CLIENT_LOG__CONSOLE__*` |
| Main file `logs/app.log` | off, DEBUG, `json` | `CLUSTER_CLIENT_LOG__FILE__*` |
| Failure file `logs/failures.log` | on, one JSON line per failed request | `CLUSTER_CLIENT_LOG__FAILURE_FILE__*` |

Every line of a request carries the `trace_id`; find a failure by the trace id of its `traceresponse`:

```bash
grep '"trace_id": "<trace id>"' logs/failures.log
```

In code, logging is done by decorators:

```python
from app.logger.decorators import log_debug, log_info


@log_info(inputs=("request.method", "request.url"), outputs=("status_code",))
@log_debug
def send_to_cluster(*, request: ClusterRequest, ...) -> ClusterResponse: ...
```

- `@log_debug` (every function): DEBUG lines with all arguments, and the return value or the error.
- `@log_info(inputs=..., outputs=...)` (key steps): one INFO line with the chosen values and the duration.

## Telemetry

Tracing is OpenTelemetry. The `traceparent` from the manager is always continued to the cluster and returned
in `traceresponse`, and every log line carries its `trace_id`; this needs no setting.

Requests to `CLUSTER_CLIENT_LOG__QUIET_PATHS` (the OpenShift probes `/health/live` and `/health/ready`) write no
log line below `CLUSTER_CLIENT_LOG__QUIET_KEPT_LEVEL` (WARNING) and get no trace; their failures are still
written.

The service itself never talks to Elastic. In Helm, `collector.enabled` adds an OpenTelemetry Collector
container to the pod that sends both to Elasticsearch:

- **logs**: the service writes every log line at `collector.logLevel` (default DEBUG, passwords included) as
  JSON to `logs/app.log`; the collector reads that file;
- **traces**: the service sends them to the collector at `127.0.0.1:4318`.

```yaml
collector:
  enabled: true
  elasticsearch:
    endpoint: https://elastic.<domain>:9200
```

Everything from this service, in every network, goes to the same data streams: `logs-cluster_client.otel-default`
and `traces-cluster_client.otel-default`. The Elastic user needs to write to them.

```bash
helm upgrade --install cluster-client ./helm -f helm/networks/<network>.yaml \
  --set collector.elasticsearch.username=<user> --set collector.elasticsearch.password="$ELASTIC_PASSWORD" ...
```

The collector image (`otel/opentelemetry-collector-contrib`, `collector.image.tag`) is pulled from the same
registry as the service: `<image.registry>.<domain>/<collector.image.repository>`. Its configuration is
`helm/templates/configmap-collector.yaml`. It remembers how far it read `app.log` (in a pod-lifetime
`emptyDir`), so a collector restart sends no line twice; the Elastic username and password are in their own Secret, never in
the service's environment.

## Tests

```bash
pytest
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
helm lint helm -f helm/networks/<network>.yaml
helm upgrade --install cluster-client helm -f helm/networks/<network>.yaml
```

`helm/values.yaml` holds what every network shares. `helm/networks/<network>.yaml` holds only what differs in
one network: `domain` (required), and if needed `image.tag` or `route.host`. `helm/values.schema.json` rejects
any unknown key or invalid value.

- image: `<image.registry>.<domain>/<image.repository>:<image.tag>` (empty tag: the chart's `appVersion`)
- route host: `route.host` if set, else `<route.name>.<domain>`

The three runtime files are read from `helm/files/` (`response-schema.json`, `ignored-fields.json`,
`redacted-fields.json`) and mounted at `mounts.files`. To change one, replace the file there and run
`helm upgrade` again; the pods restart with it.

| Key | Content |
|---|---|
| `domain` | the network's domain: suffix of the Artifactory host and of the route host |
| `image` | `registry`, `repository`, `tag`, `pullPolicy` |
| `route` | OpenShift Route: `name`, `host` (overrides `<name>.<domain>`), `tls` |
| `config` | `CLUSTER_CLIENT_*` env vars, rendered into a ConfigMap |
| `secret` | `CLUSTER_CLIENT_*` env vars, rendered into a Secret; must hold `CLUSTER_CLIENT_ACCESS__USERNAME` and `CLUSTER_CLIENT_ACCESS__PASSWORD` (pass them with `--set`, never in a file in git) |
| `collector` | `enabled`, `image`, `logLevel`, `elasticsearch` (`endpoint`, `username`, `password`, `insecureSkipVerify`), `resources`: the sidecar that sends logs and traces to Elastic |
| `resources` | requests / limits |

The manager's address is the Route's host:

```bash
oc get route cluster-client -o jsonpath='{.spec.host}'
```

## Diagrams

`docs/diagrams/flow.drawio` (request flow) and `docs/diagrams/class-diagram.drawio` (classes in that flow).
