ARG PYTHON_IMAGE=python:3.14.7-slim

# stage 1: install uv, then the app and its locked dependencies into /app/.venv
FROM ${PYTHON_IMAGE} AS builder
RUN pip install --no-cache-dir uv==0.12.17
WORKDIR /app
COPY pyproject.toml uv.lock ./
COPY app ./app
RUN uv sync --frozen --no-dev --no-editable

# stage 2: the same python image, with only the installed app copied in
FROM ${PYTHON_IMAGE}
WORKDIR /app
COPY --from=builder /app/.venv /app/.venv
COPY docker/entrypoint.py ./entrypoint.py
RUN useradd --system cluster-client && mkdir logs && chown cluster-client logs
USER cluster-client
ENV PATH="/app/.venv/bin:${PATH}" \
    PYTHONUNBUFFERED=1 \
    CLUSTER_CLIENT_SERVER__HOST=0.0.0.0 \
    CLUSTER_CLIENT_SERVER__PORT=8000 \
    CLUSTER_CLIENT_LOG__FILE__PATH=/app/logs/app.log \
    CLUSTER_CLIENT_LOG__FAILURE_FILE__PATH=/app/logs/failures.log \
    CLUSTER_CLIENT_LOG__FAILURE_FILE__REDACTED_FIELDS_PATH=/etc/cluster-client/redacted-fields.json \
    CLUSTER_CLIENT_VALIDATION__SCHEMA_PATH=/etc/cluster-client/response-schema.json \
    CLUSTER_CLIENT_VALIDATION__IGNORED_FIELDS_PATH=/etc/cluster-client/ignored-fields.json
EXPOSE 8000
CMD ["python", "entrypoint.py"]
