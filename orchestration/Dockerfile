# PRISM orchestration — Dagster asset graph (ADR-001 / ADR-006)
FROM python:3.12-slim-bookworm

# Java 17 for local Spark medallion materialization inside the container.
RUN apt-get update && apt-get install -y --no-install-recommends openjdk-17-jre-headless \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY lakehouse /app/lakehouse
COPY orchestration /app/orchestration

RUN pip install --no-cache-dir \
      "pyspark>=3.5" \
      /app/lakehouse \
      "/app/orchestration[web]"

ENV PRISM_ORCH_PORT=9112 \
    PRISM_ORCH_BRONZE_ROOT=/data/bronze \
    PRISM_ORCH_WAREHOUSE_ROOT=/data/lakehouse \
    PRISM_DRIFT_MONITOR_URL=http://drift-monitor:9109 \
    PRISM_SCENARIO_URL=http://scenario-engine:9107 \
    PRISM_DAGSTER_DRIFT_RESEED=0 \
    DAGSTER_HOME=/data/dagster \
    PYTHONUNBUFFERED=1

EXPOSE 9112
VOLUME ["/data"]

HEALTHCHECK --interval=15s --timeout=5s --retries=5 --start-period=40s \
  CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:9112/')"

# Ensure DAGSTER_HOME exists on the mounted volume before starting the UI.
# Materialize locally via `python -m prism_orchestration` without this service.
CMD ["bash", "-lc", "mkdir -p \"${DAGSTER_HOME:-/data/dagster}\" && printf 'telemetry:\\n  enabled: false\\n' > \"${DAGSTER_HOME:-/data/dagster}/dagster.yaml\" && exec dagster-webserver -h 0.0.0.0 -p 9112 -m prism_orchestration.definitions"]
