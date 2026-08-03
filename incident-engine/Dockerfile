# PRISM incident-engine — per-asset circuit breaker + OPA/Rego (ADR-001 / Phase 18)
FROM python:3.12-slim-bookworm

RUN apt-get update && apt-get install -y --no-install-recommends curl ca-certificates \
    && curl -fsSL -o /usr/local/bin/opa \
         https://openpolicyagent.org/downloads/v1.4.2/opa_linux_amd64_static \
    && chmod +x /usr/local/bin/opa \
    && apt-get purge -y curl \
    && apt-get autoremove -y \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY observability/otel /app/observability/otel
COPY incident-engine /app/incident-engine
COPY incident-engine/policies/rego /policies/rego

RUN pip install --no-cache-dir \
      /app/observability/otel \
      /app/incident-engine

ENV PRISM_INCIDENT_ENGINE_PORT=9108 \
    PRISM_DATA_ROOT=/data \
    PRISM_OPA_POLICY_DIR=/policies/rego \
    PRISM_OPA_BIN=/usr/local/bin/opa \
    PYTHONUNBUFFERED=1

EXPOSE 9108
VOLUME ["/data"]

HEALTHCHECK --interval=10s --timeout=3s --retries=5 --start-period=15s \
  CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:9108/health')"

CMD ["python", "-m", "prism_incident_engine"]
