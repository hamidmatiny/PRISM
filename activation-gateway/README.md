# activation-gateway

PRISM's namesake component: **one gold table → many warehouses** behind a single
OpenAPI contract.

| | |
|---|---|
| **Port (host)** | `9103` |
| **Health** | `GET /health` |
| **Contract** | `contracts/activation-contract` |
| **Mock warehouses** | Redshift `:9110`, Snowflake `:9111` (embedded in mock mode) |
| **ADR** | [ADR-002](../docs/adr/002-multi-warehouse-activation.md) |

## Adapters

| Warehouse | Strategy | Storage mode |
|-----------|----------|--------------|
| Redshift Serverless | zero-ETL / auto-copy (COPY Parquet/Iceberg fallback) | `materialized_copy` |
| Snowflake Horizon Catalog | Iceberg REST zero-copy read of the same gold URI | `zero_copy` |

Local/CI uses HTTP mock endpoints backed by DuckDB (ADR-001). Live cloud
warehouses are never required for `docker compose up`.

## Quick start

```bash
pip install -e contracts/activation-contract -e activation-gateway
docker compose up -d --build activation-gateway
curl -s http://localhost:9103/health

GOLD_URI="file://$(pwd)/activation-gateway/fixtures/gold/asset_daily_metrics"
curl -s http://localhost:9103/v1/activate -H 'content-type: application/json' \
  -d "{\"gold_table\":\"asset_daily_metrics\",\"warehouse\":\"redshift\",\"gold_uri\":\"$GOLD_URI\"}"
curl -s http://localhost:9103/v1/activate -H 'content-type: application/json' \
  -d "{\"gold_table\":\"asset_daily_metrics\",\"warehouse\":\"snowflake\",\"gold_uri\":\"$GOLD_URI\",\"set_primary\":false}"
curl -s http://localhost:9103/v1/query -H 'content-type: application/json' \
  -d '{"table":"asset_daily_metrics","warehouse":"auto","sql":"SELECT asset_id, ping_count FROM asset_daily_metrics ORDER BY asset_id"}'
```

## Conformance

```bash
pytest -q tests/unit/test_activation_conformance.py
```

Same SQL → both adapters → equivalent canonical rows. Structural only — no
accuracy or cost claims.

## Environment

| Variable | Default | Notes |
|----------|---------|-------|
| `PRISM_ACTIVATION_GATEWAY_PORT` | `9103` | Gateway HTTP |
| `PRISM_ACTIVATION_MODE` | `mock` | `mock` embeds warehouse endpoints |
| `PRISM_MOCK_REDSHIFT_URL` | `http://127.0.0.1:9110` | Mock Redshift |
| `PRISM_MOCK_SNOWFLAKE_URL` | `http://127.0.0.1:9111` | Mock Snowflake |
| `PRISM_ACTIVATION_FIXTURE_GOLD` | package fixtures | Fallback gold root |
| `PRISM_ACTIVATION_ROUTING_PATH` | `.data/activation/routing.json` | Primary routing |
