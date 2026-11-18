# Configuration

## How a setting is named and found

- Every setting is a field of a class in `app/config/`. The root class is `Settings` in `app/config/settings.py`; each
  section is its own file (`server.py`, `access.py`, ...).
- `Settings` reads environment variables, and a `.env` file in the working directory, named
  `CLUSTER_CLIENT_<SECTION>__<FIELD>`: upper case, `__` between levels.
  - `ForwardingSettings.timeout_seconds` → `CLUSTER_CLIENT_FORWARDING__TIMEOUT_SECONDS`
  - `FailureSettings.rejected.status_code` → `CLUSTER_CLIENT_FAILURES__REJECTED__STATUS_CODE`
  - `LoggingSettings.console.level` → `CLUSTER_CLIENT_LOG__CONSOLE__LEVEL`
- An environment variable wins over `.env`. One value changes one field; the other fields keep their defaults.
- Lists and sets are JSON: `CLUSTER_CLIENT_LOG__QUIET_PATHS='["/health/live"]'`.
- A misspelled field inside a known section (`CLUSTER_CLIENT_FORWARDING__TIMEOUT_SECOND`) stops the start. A name
  without a known section (`CLUSTER_CLIENT_FOO`) is ignored.
- Every value is checked when the service starts. A wrong value stops it with the field's name.
- `run_local.py` does not read the environment or `.env`: its settings are written in the file (`NoEnvFileSettings`).
- The container image sets `SERVER__HOST`, `SERVER__PORT`, the three `VALIDATION__*_PATH` and the two `LOG__*__PATH`
  (`docker/Dockerfile`). The Helm chart sets the port and the five paths again from its values
  (see [deployment.md](deployment.md)).

The only required settings are `CLUSTER_CLIENT_ACCESS__USERNAME` and `CLUSTER_CLIENT_ACCESS__PASSWORD`.

## Every setting

The names below leave out the `CLUSTER_CLIENT_` prefix.

### `SERVER__*` (`app/config/server.py`)

| Field | Default | Meaning |
|---|---|---|
| `HOST` | `127.0.0.1` | Address uvicorn listens on (`0.0.0.0` in the image) |
| `PORT` | `8000` | Port, 1 to 65535 |
| `SERVER_HEADER` | `false` | Send uvicorn's `server` header |
| `DATE_HEADER` | `false` | Send uvicorn's `date` header |

### `APPLICATION__*` (`app/config/application.py`)

| Field | Default | Meaning |
|---|---|---|
| `TITLE` | `cluster-client` | Title of `/docs` |

### `ACCESS__*` (`app/config/access.py`)

| Field | Default | Meaning |
|---|---|---|
| `USERNAME` | required | The manager's user. No `:` |
| `PASSWORD` | required | The manager's password. Keep it in a Secret, never in a file in git |
| `HEADER` | `authorization` | The header that carries `<scheme> base64(username:password)` |
| `SCHEME` | `Basic` | Compared in any case |
| `CHALLENGE_HEADER` | `www-authenticate` | Sent on 401 |
| `REALM` | `cluster-client` | The realm in the challenge. No `"` |

### `HEADERS__*` (`app/config/headers.py`)

| Field | Default | Meaning |
|---|---|---|
| `METHOD` | `x-edge-method` | Header with the method to send |
| `URL` | `x-edge-url` | Header with the URL to call |
| `TARGET_PREFIX` | `x-target-` | Headers with this prefix go to the target without it |
| `REFUSED_TARGET_HEADERS` | `connection`, `content-length`, `host`, `keep-alive`, `proxy-authenticate`, `proxy-authorization`, `proxy-connection`, `te`, `trailer`, `transfer-encoding`, `upgrade` | Names (after the prefix) that are refused with `invalid_request` |
| `REFUSED_REASON` | `{headers}: nameless, hop-by-hop and framing headers are never sent to the target` | The reason; `{headers}` is the only placeholder |
| `DOCUMENTED_TARGET_HEADERS` | `["authorization", "content-type"]` | `x-target-*` headers shown in `/docs` (for "Try it out"); any other is sent too |

The service stops at startup when `METHOD`, `URL` or `ACCESS__HEADER` starts with `TARGET_PREFIX`.

### `VALIDATION__*` (`app/config/validation.py`)

| Field | Default | Meaning |
|---|---|---|
| `SCHEMA_PATH` | `helm/files/response-schema.json` | The firewall's JSON Schema. In the image: `/etc/cluster-client/response-schema.json` |
| `IGNORED_FIELDS_PATH` | `helm/files/ignored-fields.json` | Field paths removed from every answer before the check |
| `REDACTED_FIELDS_PATH` | `helm/files/redacted-fields.json` | Field paths left out of a rejection's `reason` and of the failure file |

The three files are read once, at startup. A field path looks like `$.a.b` or `$[*].a` (`[*]` is every item of a
list). An index like `[0]`, or a path that ends in `[*]`, stops the start.

### `FORWARDING__*` (`app/config/forwarding.py`)

| Field | Default | Meaning |
|---|---|---|
| `CONNECT_TIMEOUT_SECONDS` | `5.0` | Connect timeout. A connect timeout is `connection_failed` (not sent) |
| `TIMEOUT_SECONDS` | `28.0` | The whole call to the target, connect included. Must be longer than the connect timeout. Keep it below the manager's own timeout (35 s) |
| `EDGE_HEADER_PREFIX` | `x-edge-` | Target headers with this prefix are never returned |
| `RECOMPUTED_RESPONSE_HEADERS` | `content-length`, `content-encoding`, `transfer-encoding`, `connection` | Target headers not returned (the server sets its own) |

### `FAILURES__*` (`app/config/failures.py`)

| Field | Default | Meaning |
|---|---|---|
| `INVALID_REQUEST__STATUS_CODE`, `__ERROR_CODE` | `400`, `invalid_request` | |
| `UNAUTHORIZED__...` | `401`, `unauthorized` | |
| `REJECTED__...` | `502`, `response_rejected` | |
| `CONNECTION_FAILED__...` | `502`, `connection_failed` | |
| `NO_RESPONSE__...` | `504`, `timeout` | |
| `INTERNAL_ERROR__...` | `500`, `internal_error` | |
| `ERROR_HEADER` | `x-edge-error` | Must start with `FORWARDING__EDGE_HEADER_PREFIX` |
| `TARGET_STATUS_HEADER` | `x-edge-target-status` | Must start with `FORWARDING__EDGE_HEADER_PREFIX` |
| `CONTENT_TYPE_HEADER`, `CONTENT_TYPE` | `content-type`, `application/json` | |
| `SHORTENED_FIELD_PREFIX` | `...` | Starts a `field` cut from the start |
| `UNSENT_CHARACTERS_MESSAGE` | `{count} more characters were not sent` | Last part of a cut `reason` |
| `NOT_JSON_RULE`, `NOT_JSON_REASON` | `not_json`, `the response body is not JSON: {error}` | |
| `TOO_DEEP_RULE`, `TOO_DEEP_REASON` | `too_deep`, `the response body is nested too deeply to be checked` | |
| `REDACTED_REASON` | `the failing value is a redacted field` | The `reason` when the failing value is a redacted field |

Status codes must be 400 to 599. A text with an unknown placeholder stops the start. At startup, every error code,
rule, the unsent message and the `...` prefix must also fit the limits of `response-schema.json`.

### `LOG__*` (`app/config/logging.py`)

| Field | Default | Meaning |
|---|---|---|
| `LEVEL` | `INFO` | The lowest level any handler can write. Set `DEBUG` to get DEBUG lines anywhere |
| `QUIET_PATHS` | `["/health/live", "/health/ready"]` | Requests to these paths log nothing below `QUIET_KEPT_LEVEL` and get no trace span |
| `QUIET_KEPT_LEVEL` | `WARNING` | |
| `CONSOLE__ENABLED`, `__LEVEL`, `__FORMAT` | `true`, `INFO`, `line` | Terminal (stdout). Format `line` or `json` |
| `FILE__ENABLED`, `__LEVEL`, `__FORMAT` | `false`, `DEBUG`, `json` | Main file |
| `FILE__PATH`, `__MAX_BYTES`, `__BACKUP_COUNT` | `logs/app.log`, `10485760`, `5` | Rotated at 10 MiB, 5 old files kept |
| `FAILURE_FILE__ENABLED`, `__LEVEL`, `__FORMAT` | `true`, `WARNING`, `json` | One line per failure |
| `FAILURE_FILE__PATH`, `__MAX_BYTES`, `__BACKUP_COUNT` | `logs/failures.log`, `10485760`, `5` | |
| `FAILURE_FILE__LOGGER_NAME` | `cluster_client.failures` | |
| `FORMATTING__LINE_PATTERN` | `%(asctime)s \| %(levelname)-8s \| %(name)s \| trace_id=%(otelTraceID)s \| %(message)s` | The `line` format |
| `FORMATTING__DATE_FORMAT` | `%Y-%m-%dT%H:%M:%S%z` | |

The DEBUG file holds everything, the target's password included, on purpose. To turn it on:
`CLUSTER_CLIENT_LOG__LEVEL=DEBUG` and `CLUSTER_CLIENT_LOG__FILE__ENABLED=true`.

### `TELEMETRY__*` (`app/config/telemetry.py`)

| Field | Default | Meaning |
|---|---|---|
| `SERVICE_NAME` | `cluster-client` | `service.name` of the spans |
| `EXPORT_ENABLED` | `false` | Send spans over OTLP/HTTP |
| `OTLP_ENDPOINT` | `http://localhost:4318` | No trailing `/` |
| `TRACES_PATH` | `/v1/traces` | |
| `TRACE_HEADER`, `TRACE_RESPONSE_HEADER`, `EXPOSED_HEADERS_HEADER` | `traceparent`, `traceresponse`, `access-control-expose-headers` | Names shown in `/docs` only; OpenTelemetry sets the real headers |
