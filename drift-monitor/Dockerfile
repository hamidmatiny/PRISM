# PRISM drift-monitor — honest-baseline drift detection (ADR-001 / Phase 16)
FROM python:3.12-slim-bookworm

WORKDIR /app
COPY observability/otel /app/observability/otel
COPY drift-monitor /app/drift-monitor

RUN pip install --no-cache-dir \
      /app/observability/otel \
      /app/drift-monitor

ENV PRISM_DRIFT_MONITOR_PORT=9109 \
    PYTHONUNBUFFERED=1

EXPOSE 9109

HEALTHCHECK --interval=10s --timeout=3s --retries=5 --start-period=15s \
  CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:9109/health')"

CMD ["python", "-m", "prism_drift_monitor"]
