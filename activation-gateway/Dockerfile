# PRISM activation-gateway — Redshift + Snowflake adapters (mock endpoints in CI)
# ADR-001: no real warehouse credentials required for local/compose.
FROM python:3.12-slim-bookworm

WORKDIR /app
COPY contracts/activation-contract /app/contracts/activation-contract
COPY activation-gateway /app/activation-gateway

RUN pip install --no-cache-dir \
      /app/contracts/activation-contract \
      /app/activation-gateway

ENV PRISM_ACTIVATION_GATEWAY_PORT=9103 \
    PRISM_ACTIVATION_MODE=mock \
    PRISM_ACTIVATION_EMBEDDED_MOCKS=1 \
    PRISM_MOCK_REDSHIFT_URL=http://127.0.0.1:9110 \
    PRISM_MOCK_SNOWFLAKE_URL=http://127.0.0.1:9111 \
    PRISM_DATA_ROOT=/data \
    PRISM_LAKEHOUSE_ROOT=/data/lakehouse \
    PRISM_ACTIVATION_FIXTURE_GOLD=/app/activation-gateway/fixtures/gold \
    PRISM_ACTIVATION_ROUTING_PATH=/data/activation/routing.json \
    PYTHONUNBUFFERED=1

EXPOSE 9103 9110 9111
VOLUME ["/data"]

HEALTHCHECK --interval=10s --timeout=3s --retries=5 --start-period=25s \
  CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:9103/health')"

CMD ["python", "-m", "prism_activation_gateway"]
