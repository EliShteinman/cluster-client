# cluster-client

Runs inside each network. The manager sends it a request; it sends that request to the target named in it (today
the Redis Enterprise REST API of a cluster), checks the answer against the firewall's JSON schema, and returns it.

## Installation

```bash
uv sync
uv run pre-commit install
```

## Run

```bash
python run_local.py
```

`run_local.py` sets local credentials (`manager` / `local-password`) and its other settings in code; it ignores
`.env` (`NoEnvFileSettings`). Everywhere else the service does not start without
`CLUSTER_CLIENT_ACCESS__USERNAME` and `CLUSTER_CLIENT_ACCESS__PASSWORD` (no defaults). To run locally with settings
from env and `.env`, as in the container:

```bash
cp .env.example .env   # then fill in the username and password
PYTHONPATH=. uv run python docker/entrypoint.py
```

The app is built by `app.main.create_app(settings)`. Each environment passes its own `Settings`:

| Environment | Entry | Settings come from |
|---|---|---|
| Local | `run_local.py` | written in the file |
| Docker / Helm | `docker/entrypoint.py` | `CLUSTER_CLIENT_*` env vars (see Configuration) |

## Usage

`POST /` with the manager's own credentials, the call to make in the tool's own headers, and the headers for the
target marked with the `x-target-` prefix:

```bash
curl -X POST http://127.0.0.1:8000/ \
  -H "authorization: Basic $(printf 'manager:<password>' | base64)" \
  -H "x-edge-method: GET" \
  -H "x-edge-url: https://cluster.example:9443/v1/bdbs" \
  -H "x-target-authorization: Basic <credentials>"
```

- `authorization` is the manager's access: `Basic base64(username:password)`, the scheme in any case. It is never
  sent to the target. In `/docs`, click **Authorize** and enter the same username and password to try `POST /`.
- `x-edge-method` (any HTTP method) and `x-edge-url` (an http or https URL, any length) are read, never sent.
  Both go to the target as `requests` sends them (the method in upper case, the URL re-quoted), query string
  included.
- Every header that starts with `x-target-` is sent to the target without the prefix:
  `x-target-authorization` → `authorization`, `x-target-content-type` → `content-type`,
  `x-target-cluster-state-id` → `cluster-state-id`. No other header reaches the target, so a target without
  credentials simply gets no `authorization`. An `x-target-` header that names a hop-by-hop or framing header
  (`host`, `content-length`, `transfer-encoding`, `connection`, …), or no header at all (exactly `x-target-`), is
  refused with `invalid_request`.
- The request body, if any, is sent to the target as is. An incoming `traceparent` is continued to the target, and
  the response carries `traceresponse`.

| Case | Status | `x-edge-error` | Body |
|---|---|---|---|
| Answer matches the schema | the target's | none | the target's: byte for byte, or re-encoded when an ignored field was removed; its headers, except any `x-edge-*` and those the server recomputes (`content-length`, `content-encoding`, `transfer-encoding`, `connection`) |
| Answer is not standard JSON (`NaN`, `Infinity` included), too deeply nested, or breaks the schema | 502 | `response_rejected` | `{"error", "rule", "field", "reason"}` |
| Request surely did not reach the target (refused, DNS, connect timeout) | 502 | `connection_failed` | `{"error", "reason"}` |
| Request may have been sent, no full answer within the total timeout (timeout, connection cut, TLS error) | 504 | `timeout` | `{"error", "reason"}` |
| `authorization` is missing or wrong (nothing is sent to the target) | 401 | `unauthorized` | `{"error", "reason"}`, with `www-authenticate: Basic realm="cluster-client"` |
| An own header is missing or invalid, a refused `x-target-` header, or a URL/header the HTTP library refuses before sending | 400 | `invalid_request` | `{"error", "reason"}` |
| Wrong path or method on the cluster client | 404, 405 | `invalid_request` | `{"error", "reason"}` |
| Unexpected error inside the cluster client | 500 | `internal_error` | `{"error", "reason"}` (the error and its traceback) |

`x-edge-error` is on every answer the cluster client made itself, and never on a target answer (an `x-edge-*`
header sent by the target is dropped). A `response_rejected` answer also carries the target's status in
`x-edge-target-status`. Status codes, error codes and header names are set by `CLUSTER_CLIENT_FAILURES__*` and
`CLUSTER_CLIENT_HEADERS__*`.

Every body the cluster client writes itself passes the firewall's response schema:

```json
{"error": "response_rejected", "rule": "anyOf", "field": "$.shard_list", "reason": ["...", "..."]}
```

- `rule`: the JSON Schema keyword that failed (`not_json` when the answer is not JSON, `too_deep` when it is
  nested too deeply to check); rejections only.
- `field`: the failing field; longer than the schema allows for `field` (256 today), it is cut from the start
  and begins with `...`.
- `reason`: the whole explanation in parts as long as the schema allows for one item of `reason` (256 today);
  joined, they are the full text. Above the number of items the schema allows (500 today), the last part says
  how many characters were not sent.
- These limits are read from the schema at startup, never configured. If the schema sets no limit for one of
  these fields (`maxLength` of `error`, `rule`, `field` and of each item of `reason`, `maxItems` of `reason`), is
  recursive, or cannot hold such a body, the service does not start.
- The explanation is built after removing the redacted fields, so no listed password reaches it; a failure in a
  redacted field itself is explained without its value. The original explanation is in the DEBUG log.

Three files are read at startup; replace them without touching the code or the image:

| File | Setting | Content |
|---|---|---|
| `helm/files/response-schema.json` | `CLUSTER_CLIENT_VALIDATION__SCHEMA_PATH` | the JSON Schema every answer must match, checked by the draft it declares (`$schema`) |
| `helm/files/ignored-fields.json` | `CLUSTER_CLIENT_VALIDATION__IGNORED_FIELDS_PATH` | field paths removed before the check |
| `helm/files/redacted-fields.json` | `CLUSTER_CLIENT_VALIDATION__REDACTED_FIELDS_PATH` | field paths left out of the failure log and of a rejection's explanation (passwords) |

Ignored and redacted fields use the same format as `field` in a rejection, with `[*]` for every item of a list:

```json
["$[*].shards_placement", "$.endpoints[*].internal_id"]
```

When a field is removed, the answer is re-encoded; otherwise it is returned byte for byte.

Real cluster answers, passwords replaced, are kept in `tests/support/cluster_samples/`; a test runs every one of
them through the three files.

Health probes: `GET /health/live`, `GET /health/ready`.

The OpenAPI description of `POST /` (the forwarding rule, the request headers, every failure status with its body
and headers, from the settings in use) is served at `/openapi.json` and `/docs`.

## Configuration

Every setting is an env var (or a line in `.env`) named `CLUSTER_CLIENT_<SECTION>__<FIELD>`, upper case, with
`__` between nested levels. The sections and fields, with their defaults, are the classes in `app/config/`
(`Settings` in `app/config/settings.py` lists the sections). For example:

```bash
CLUSTER_CLIENT_FORWARDING__TIMEOUT_SECONDS=20          # ForwardingSettings.timeout_seconds
CLUSTER_CLIENT_FAILURES__REJECTED__STATUS_CODE=422     # FailureSettings.rejected.status_code
```

Only `CLUSTER_CLIENT_ACCESS__USERNAME` and `CLUSTER_CLIENT_ACCESS__PASSWORD` are required; set any other only to
change its default. The usual ones are in `.env.example`. In the image, `SERVER__HOST`, `SERVER__PORT`,
`VALIDATION__*_PATH` and `LOG__*__PATH` are set already. Lists are JSON (`["a", "b"]`). A misspelled field inside
a section (`CLUSTER_CLIENT_FORWARDING__TIMEOUT_SECOND`) stops the service at startup; a name without a known
section (`CLUSTER_CLIENT_FOO`) is ignored.

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


@log_info(inputs=("path",))
@log_debug
def load_schema(*, path: Path) -> Validator: ...
```

- `@log_debug` (every function): DEBUG lines with all arguments, and the return value or the error.
- `@log_info(inputs=..., outputs=...)` (key steps): one INFO line with the chosen values and the duration.

## Telemetry

Tracing is OpenTelemetry. The `traceparent` from the manager is always continued to the target and returned
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
  --set secret.CLUSTER_CLIENT_ACCESS__USERNAME=<manager user> \
  --set secret.CLUSTER_CLIENT_ACCESS__PASSWORD="$MANAGER_PASSWORD" \
  --set collector.elasticsearch.username=<user> --set collector.elasticsearch.password="$ELASTIC_PASSWORD"
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
docker run --rm -p 8000:8000 --read-only -v /app/logs -v "$PWD/helm/files:/etc/cluster-client:ro" \
  -e CLUSTER_CLIENT_ACCESS__USERNAME=manager -e CLUSTER_CLIENT_ACCESS__PASSWORD=<password> cluster-client:0.1.0
```

## Helm

```bash
helm lint helm -f helm/networks/<network>.yaml \
  --set secret.CLUSTER_CLIENT_ACCESS__USERNAME=<manager user> --set secret.CLUSTER_CLIENT_ACCESS__PASSWORD=x
helm upgrade --install cluster-client helm -f helm/networks/<network>.yaml \
  --set secret.CLUSTER_CLIENT_ACCESS__USERNAME=<manager user> \
  --set secret.CLUSTER_CLIENT_ACCESS__PASSWORD="$MANAGER_PASSWORD"
```

`values.schema.json` requires both `secret` keys, so `helm lint` needs them too (any value).

`helm/values.yaml` holds what every network shares. `helm/networks/<network>.yaml` holds only what differs in
one network: `domain` (required), and if needed `image.tag` or `route.host`. `helm/values.schema.json` rejects
any unknown key or invalid chart value; `config`/`secret` keys must be `CLUSTER_CLIENT_*` names, except the host the image sets and
the port, file paths and log paths the chart sets from `containerPort`, `files` and `logs`.

- image: `<image.registry>.<domain>/<image.repository>:<image.tag>` (empty tag: the chart's `appVersion`)
- route host: `route.host` if set, else `<route.name>.<domain>`

The three runtime files are read from `helm/files/` (`response-schema.json`, `ignored-fields.json`,
`redacted-fields.json`) and each is mounted at its own path: `files.schema`, `files.ignoredFields`,
`files.redactedFields`. The logs go to `logs.directory` (shared with the collector), as `logs.app` and
`logs.failures`. To change a file, replace it there and run `helm upgrade` again; the pods restart with it.

| Key | Content |
|---|---|
| `domain` | the network's domain: suffix of the Artifactory host and of the route host |
| `image` | `registry`, `repository`, `tag`, `pullPolicy` |
| `route` | OpenShift Route: `name`, `host` (overrides `<name>.<domain>`), `tls` |
| `config` | `CLUSTER_CLIENT_*` env vars (strings), rendered into a ConfigMap; the service checks the values when it starts, and stops on a misspelled field inside a section |
| `secret` | `CLUSTER_CLIENT_*` env vars, rendered into a Secret; must hold `CLUSTER_CLIENT_ACCESS__USERNAME` and `CLUSTER_CLIENT_ACCESS__PASSWORD` (pass them with `--set`, never in a file in git) |
| `collector` | `enabled`, `image`, `logLevel`, `elasticsearch` (`endpoint`, `username`, `password`, `insecureSkipVerify`), `resources`: the sidecar that sends logs and traces to Elastic |
| `resources` | requests / limits |

The manager's address is the Route's host:

```bash
oc get route cluster-client -o jsonpath='{.spec.host}'
```

## Diagrams

`docs/diagrams/flow.drawio` (request flow) and `docs/diagrams/class-diagram.drawio` (classes in that flow).
