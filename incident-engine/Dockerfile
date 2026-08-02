# PRISM incident-engine — per-asset circuit breaker (ADR-001 / Phase 14)
FROM python:3.12-slim-bookworm

WORKDIR /app
COPY observability/otel /app/observability/otel
COPY incident-engine /app/incident-engine

RUN pip install --no-cache-dir \
      /app/observability/otel \
      /app/incident-engine

ENV PRISM_INCIDENT_ENGINE_PORT=9108 \
    PRISM_DATA_ROOT=/data \
    PYTHONUNBUFFERED=1

EXPOSE 9108
VOLUME ["/data"]

HEALTHCHECK --interval=10s --timeout=3s --retries=5 --start-period=15s \
  CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:9108/health')"

CMD ["python", "-m", "prism_incident_engine"]
