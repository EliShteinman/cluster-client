# cluster-client

cluster-client runs inside a firewalled network. The manager sends it one request; cluster-client sends that request
to the target named in it (today the Redis Enterprise REST API of a cluster) and returns the answer, but only if
the firewall would let it through. Otherwise it answers with an error that does pass the firewall.

How it works: [docs/architecture.md](docs/architecture.md). Every page: [docs/README.md](docs/README.md).

## Requirements

- [uv](https://docs.astral.sh/uv/) (it installs Python 3.14 if needed)
- To build and deploy: Docker, Helm 3, `oc`

## Install

```bash
uv sync
uv run pre-commit install
```

There is no `uv.lock` in git on purpose: `uv sync` resolves `pyproject.toml` against your own package index. Run it
once after cloning.

## Run locally

```bash
uv run python run_local.py
```

The service listens on `http://127.0.0.1:8000`. `run_local.py` has its settings in the file: username `manager`,
password `local-password`, DEBUG logs to the terminal and to `logs/local.log`, failures to `logs/local-failures.log`.
It does not read `.env`.

To run with settings from the environment, as the container does:

```bash
cp .env.example .env    # fill in CLUSTER_CLIENT_ACCESS__USERNAME and CLUSTER_CLIENT_ACCESS__PASSWORD
PYTHONPATH=. uv run python docker/entrypoint.py
```

## Try it

Start a small target that serves JSON files, in a second terminal:

```bash
mkdir -p /tmp/target
echo '{"uid": 1, "name": "db1"}' > /tmp/target/bdb.json
echo '{"uid": 1, "bad key": true}' > /tmp/target/bad.json
python3 -m http.server 9000 --bind 127.0.0.1 --directory /tmp/target
```

Call it through cluster-client:

```bash
curl -i -X POST http://127.0.0.1:8000/ -u manager:local-password \
  -H "x-edge-method: GET" -H "x-edge-url: http://127.0.0.1:9000/bdb.json"
```

The answer is the target's: `200`, its body, and a `traceresponse` header. Ask for `bad.json` instead and the answer
is `502` with `x-edge-error: response_rejected`, because `"bad key"` breaks the firewall's schema:

```json
{"error":"response_rejected","rule":"additionalProperties","field":"$","reason":["'bad key' does not match any of the regexes: '^(?!acl$)[A-Za-z0-9_-]{1,64}$'"]}
```

The live contract, with "Try it out", is at http://127.0.0.1:8000/docs (click **Authorize** and enter the same
username and password).

## Call it

`POST /` with these headers:

| Header | Required | Meaning |
|---|---|---|
| `authorization` | yes | `Basic base64(username:password)` of the manager. Never sent to the target |
| `x-edge-method` | yes | The method to send (`GET`, `PUT`, ...) |
| `x-edge-url` | yes | The http or https URL to call, query included |
| `x-target-<name>` | no | Sent to the target as `<name>`: `x-target-authorization` → `authorization`, `x-target-content-type` → `content-type`. No other header reaches the target |
| `traceparent` | no | The manager's trace. The call to the target and every log line continue it |

The request body, if any, goes to the target as it is. `x-target-` alone, and `x-target-host`,
`x-target-content-length`, `x-target-transfer-encoding`, `x-target-connection` and the other hop-by-hop headers, are
refused with `400`.

The answer:

| Case | Status | `x-edge-error` |
|---|---|---|
| The target's answer passes the schema | the target's | none: the target's headers and body |
| Wrong or missing `authorization` | 401 | `unauthorized` |
| Wrong own header or refused `x-target-*` header; wrong path (404) or method (405) | 400, 404, 405 | `invalid_request` |
| The call surely did not reach the target | 502 | `connection_failed` |
| No full answer within 28 seconds: the call may have been done | 504 | `timeout` |
| The target answered, but its body would be blocked by the firewall | 502 | `response_rejected` (+ `x-edge-target-status`) |
| A bug in cluster-client | 500 | `internal_error` |

Every failure, with what it means for the manager: [docs/failures.md](docs/failures.md).

Health probes (no credentials): `GET /health/live`, `GET /health/ready`.

## Configure

Every setting is an environment variable (or a line in `.env`) named `CLUSTER_CLIENT_<SECTION>__<FIELD>`, for
example:

```bash
CLUSTER_CLIENT_FORWARDING__TIMEOUT_SECONDS=20
CLUSTER_CLIENT_FAILURES__REJECTED__STATUS_CODE=422
```

Only `CLUSTER_CLIENT_ACCESS__USERNAME` and `CLUSTER_CLIENT_ACCESS__PASSWORD` are required. The usual ones are in
`.env.example`; every setting, with its default, is in [docs/configuration.md](docs/configuration.md).

Three files are read at startup. Change them without touching the code or the image:

| File | Content |
|---|---|
| `helm/files/response-schema.json` | The firewall's JSON Schema. Every answer must match it |
| `helm/files/ignored-fields.json` | Field paths removed from every answer before the check |
| `helm/files/redacted-fields.json` | Field paths (passwords) left out of a rejection's explanation and of the failure file |

A field path looks like `$.name` or `$[*].shards_placement` (`[*]`: every item of a list). Real Redis answers,
passwords replaced, are in `tests/support/cluster_samples/`; a test runs every one of them through the three files.

## Logs and traces

| Output | Default | Setting |
|---|---|---|
| Terminal | on, INFO, `line` format | `CLUSTER_CLIENT_LOG__CONSOLE__*` |
| `logs/app.log` | off; JSON | `CLUSTER_CLIENT_LOG__FILE__*` |
| `logs/failures.log` | on; one JSON line per failure, never cut | `CLUSTER_CLIENT_LOG__FAILURE_FILE__*` |

The root level is INFO (`CLUSTER_CLIENT_LOG__LEVEL`). For the full DEBUG log, with every call and its data
(passwords included), set both:

```bash
CLUSTER_CLIENT_LOG__LEVEL=DEBUG
CLUSTER_CLIENT_LOG__FILE__ENABLED=true
```

Every line of a call carries its `trace_id`, the same id as in the answer's `traceresponse`
(`00-<trace_id>-<span_id>-<flags>`). Find a failure by it:

```bash
grep '"trace_id": "<trace_id>"' logs/failures.log
```

Probe requests (`/health/live`, `/health/ready`) write no line below WARNING and get no trace.

In Helm, an optional collector sends the logs and the traces to Elasticsearch: [docs/deployment.md](docs/deployment.md).

## Tests and linters

```bash
uv run pytest
uv run ruff check .
uv run ruff format .
uv run basedpyright
uv run lint-imports
```

`uv run pre-commit run --all-files` runs the four checks; after `uv run pre-commit install` they run on every commit.

## Docker

```bash
docker build -f docker/Dockerfile -t cluster-client:0.1.0 .
docker run --rm -p 8000:8000 --read-only -v /app/logs -v "$PWD/helm/files:/etc/cluster-client:ro" \
  -e CLUSTER_CLIENT_ACCESS__USERNAME=manager -e CLUSTER_CLIENT_ACCESS__PASSWORD=<password> cluster-client:0.1.0
```

The image holds the code only. The three files are mounted at `/etc/cluster-client/`.

## Deploy with Helm

One values file per network in `helm/networks/<network>.yaml`, with at least `domain` (see
`helm/networks/example.yaml`). The image is pulled from `artifactory.<domain>/cluster-client:<tag>`.

```bash
helm lint helm -f helm/networks/<network>.yaml \
  --set secret.CLUSTER_CLIENT_ACCESS__USERNAME=<manager user> \
  --set secret.CLUSTER_CLIENT_ACCESS__PASSWORD="$MANAGER_PASSWORD"

helm upgrade --install cluster-client helm -f helm/networks/<network>.yaml \
  --set secret.CLUSTER_CLIENT_ACCESS__USERNAME=<manager user> \
  --set secret.CLUSTER_CLIENT_ACCESS__PASSWORD="$MANAGER_PASSWORD"

oc get route cluster-client -o jsonpath='{.spec.host}'    # the manager's address
```

`helm lint` needs the two `secret` values too (any value). Never put the password in a file in git. To change one of
the three files, edit it in `helm/files/` and run `helm upgrade` again; the pod restarts with it.

Values, the pod, volumes, environment and the Elastic collector: [docs/deployment.md](docs/deployment.md).
