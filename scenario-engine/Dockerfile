# PRISM scenario-engine — seeded audited chaos (ADR-001 / ADR-005)
FROM python:3.12-slim-bookworm

WORKDIR /app
COPY contracts/telemetry-schema /app/contracts/telemetry-schema
COPY scenario-engine /app/scenario-engine

RUN pip install --no-cache-dir \
      /app/contracts/telemetry-schema \
      /app/scenario-engine

ENV PRISM_SCENARIO_PORT=9107 \
    PRISM_SCENARIO_SEED=42 \
    PRISM_DATA_ROOT=/data \
    PYTHONUNBUFFERED=1

EXPOSE 9107
VOLUME ["/data"]

HEALTHCHECK --interval=10s --timeout=3s --retries=5 --start-period=15s \
  CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:9107/health')"

CMD ["python", "-m", "prism_scenario_engine"]
