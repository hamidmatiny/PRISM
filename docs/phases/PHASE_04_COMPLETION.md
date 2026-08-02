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
- [ADR-002](../adr/002-multi-warehouse-activation.md) — why both warehouses.
- Gold Parquet fixtures under `activation-gateway/fixtures/gold/` (**CI unit path only** — see below).

## Which gold URI did conformance use?

| Path | Gold source | Used by |
|------|-------------|---------|
| **CI unit conformance (as shipped)** | Separately generated synthetic fixture: `activation-gateway/fixtures/gold/asset_daily_metrics` (`metric_date=2026-08-01`, ping counts 12/9/15) | `tests/unit/test_activation_conformance.py` |
| **Live pipeline verification (post-ship check)** | Real bind-mounted gold from ingest → bronze → silver → gold: `file:///data/lakehouse/gold/asset_daily_metrics` (= host `./.data/lakehouse/gold/...`). Matches `main_gold.asset_daily_metrics` in `.data/prism_dbt.duckdb` | Manual activate+query against running `activation-gateway` |

**Answer:** the automated suite pointed at the **fixture**, not live Phase 1/2 gold. Live gold was then re-verified separately (below).

## Verified

| Check | Result |
|-------|--------|
| `make phase4-check` (55 unit tests) | Green (fixture gold) |
| `docker compose up -d --build activation-gateway` | `Up (healthy)` on `:9103` (mocks `:9110`/`:9111`) |
| `GET /health` | `status=ok`, both mock warehouses `ok` |
| Fixture gold activate+query both adapters | Equal rows (synthetic 12/9/15) |
| **Live gold** `file:///data/lakehouse/gold/asset_daily_metrics` | Activate both adapters → `row_count=3`; identical SELECT rows: `PRISM-AST-001/2026-08-02/28`, `002/17`, `003/21` (matches Spark parquet gold **and** dbt `main_gold.asset_daily_metrics`) |
| Live storage modes | Redshift `materialized_copy` / Snowflake `zero_copy`; row sets equal |

## Explicit non-claims

- Mock warehouses are **not** real Redshift Serverless or Snowflake accounts.
- Tests assert **structural / logical equivalence** only — no invented $/query or latency figures (Vulcan-style discipline).
- CI continues to use fixture gold so the default matrix does not depend on a populated `.data/` lakehouse (ADR-001).

## Deferred

| Item | Lands in |
|------|----------|
| Control-plane UI consuming activation APIs | Phase 5 |
| Live Redshift zero-ETL / Snowflake Horizon credentials | Manual / Phase 6+ (human-gated) |
| Copilot tools over activation query | Phase 9 |

## How to verify

```bash
# CI / unit (fixture gold)
pip install -e contracts/activation-contract -e activation-gateway
pytest -q tests/unit/test_activation_conformance.py tests/unit/test_activation_gateway.py

# Live gold on bind-mounted .data (requires prior ingest → lakehouse → dbt)
docker compose up -d --build activation-gateway
curl -s http://localhost:9103/health
GOLD_URI="file:///data/lakehouse/gold/asset_daily_metrics"
curl -s http://localhost:9103/v1/activate -H 'content-type: application/json' \
  -d "{\"gold_table\":\"asset_daily_metrics\",\"warehouse\":\"redshift\",\"gold_uri\":\"$GOLD_URI\"}"
curl -s http://localhost:9103/v1/activate -H 'content-type: application/json' \
  -d "{\"gold_table\":\"asset_daily_metrics\",\"warehouse\":\"snowflake\",\"gold_uri\":\"$GOLD_URI\",\"set_primary\":false}"
curl -s http://localhost:9103/v1/query -H 'content-type: application/json' \
  -d '{"table":"asset_daily_metrics","warehouse":"redshift","sql":"SELECT asset_id, CAST(metric_date AS VARCHAR) AS metric_date, ping_count FROM asset_daily_metrics ORDER BY asset_id"}'
curl -s http://localhost:9103/v1/query -H 'content-type: application/json' \
  -d '{"table":"asset_daily_metrics","warehouse":"snowflake","sql":"SELECT asset_id, CAST(metric_date AS VARCHAR) AS metric_date, ping_count FROM asset_daily_metrics ORDER BY asset_id"}'
```

## Stop

Phase 4 only. Do not start Phase 5 until explicitly requested.
