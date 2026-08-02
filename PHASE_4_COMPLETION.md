# Phase 4 completion — Activation gateway

**Date:** 2026-08-01  
**Status:** Complete (awaiting human go-ahead before Phase 5)

## What shipped

- `contracts/activation-contract/` OpenAPI **1.0.0** + Pydantic models:
  - `POST /v1/activate` — activate gold table X into warehouse Y
  - `POST /v1/query` — query table X regardless of serving warehouse (`warehouse=auto`)
  - routing + warehouse catalog endpoints
- `activation-gateway/` on host port **9103** implementing that contract.
- **Redshift adapter** — zero-ETL/auto-copy preferred, COPY Parquet fallback → `materialized_copy`.
- **Snowflake adapter** — Iceberg REST / Horizon Catalog zero-copy against the **same** gold URI → `zero_copy` (no storage duplication).
- Embedded mock warehouse HTTP endpoints on **9110** (Redshift) and **9111** (Snowflake) for local/CI (ADR-001).
- Conformance suite `tests/unit/test_activation_conformance.py` — identical SQL, equivalent results.
- [ADR-002](docs/adr/002-multi-warehouse-activation.md) — why both warehouses.
- Gold Parquet fixtures under `activation-gateway/fixtures/gold/`.

## Verified

| Check | Result |
|-------|--------|
| `make phase4-check` (55 unit tests) | Green |
| `docker compose up -d --build activation-gateway` | `Up (healthy)` on `:9103` (mocks `:9110`/`:9111`) |
| `GET /health` | `status=ok`, both mock warehouses `ok` |
| Activate fixture gold on Redshift + Snowflake | `zero_etl`/`materialized_copy` and `iceberg_rest`/`zero_copy`; `row_count=3` |
| Identical SELECT both warehouses | Equal rows (`PRISM-AST-001/002/003` ping counts) |

## Explicit non-claims

- Mock warehouses are **not** real Redshift Serverless or Snowflake accounts.
- Tests assert **structural / logical equivalence** only — no invented $/query or latency figures (Vulcan-style discipline).

## Deferred

| Item | Lands in |
|------|----------|
| Control-plane UI consuming activation APIs | Phase 5 |
| Live Redshift zero-ETL / Snowflake Horizon credentials | Manual / Phase 6+ (human-gated) |
| Copilot tools over activation query | Phase 9 |

## How to verify

```bash
pip install -e contracts/activation-contract -e activation-gateway
pytest -q tests/unit/test_activation_conformance.py tests/unit/test_activation_gateway.py
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

## Stop

Phase 4 only. Do not start Phase 5 until explicitly requested.
