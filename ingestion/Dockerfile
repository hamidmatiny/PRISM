# PRISM ingestion — local-first simulator (ADR-001: no cloud credentials required)
FROM python:3.12-slim

WORKDIR /app

COPY contracts/telemetry-schema /app/contracts/telemetry-schema
COPY observability/otel /app/observability/otel
COPY ingestion /app/ingestion

RUN pip install --no-cache-dir \
      /app/contracts/telemetry-schema \
      /app/observability/otel \
      "/app/ingestion[localstack]"

ENV PRISM_INGEST_BACKEND=file \
    PRISM_DATA_ROOT=/data \
    PRISM_EMIT_RATE=2 \
    PRISM_FAILURE_RATE=0.05 \
    PRISM_DURATION_SECONDS=0 \
    PRISM_INGESTION_PORT=9105 \
    PYTHONUNBUFFERED=1

EXPOSE 9105
VOLUME ["/data"]

HEALTHCHECK --interval=10s --timeout=3s --retries=5 --start-period=10s \
  CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:9105/health')"

CMD ["python", "-m", "prism_ingestion"]
