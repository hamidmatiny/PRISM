# Phase 2 completion — Lakehouse core

**Date:** 2026-08-01  
**Status:** Complete (awaiting human go-ahead before Phase 3)

## Direct answer: what bronze did verification use?

**Initially (first Phase 2 push): synthetic fixtures** — `lakehouse/fixtures/bronze` via `lakehouse-fixtures` / `make lakehouse-run`. That did **not** prove ingest → lakehouse wiring.

**After this follow-up: live Phase 1 ingestion bronze** — `PRISM_INGEST_BACKEND=localstack docker compose --profile localstack up -d --build`, Hive-partitioned landings under host `./.data/bronze/.../dt=2026-08-02/device=PRISM-DEV-*/`, then:

```bash
docker compose --profile lakehouse run --rm lakehouse   # reads /data/bronze (= ./.data/bronze)
cd dbt && DBT_PROFILES_DIR=$PWD dbt build --target duckdb
```

Evidence this was not fixtures:

| Source | `dt=` partition | Silver row counts |
|--------|-----------------|-------------------|
| Fixtures | `2026-08-01` (3 pings / 2 frames) | would be 3 / 2 |
| Live ingest (this run) | `2026-08-02` | **66** sensor / **36** camera; dbt `PASS=31` |

Backend stayed `localstack` through the lakehouse run (pinned via `.env`).

## Path gap found (and fixed)

**Previously:** ingestion wrote to a Docker **named volume** (`prism_prism-data`), while host Spark/dbt and `lakehouse-fixtures` used `./.data` or `./lakehouse/fixtures`. Those were **not** the same bronze path — easy to “verify” lakehouse without ever reading container-written bronze.

**Now:** compose bind-mounts `./.data:/data` for `ingestion` and `lakehouse`. Contract:

| Path | Role |
|------|------|
| `./.data/bronze` | Ingestion Hive landings (`dt=` / `device=`) |
| `./.data/lakehouse` | Silver/gold parquet from medallion |
| `lakehouse/fixtures/bronze` | CI/offline only (`lakehouse-fixtures` profile) |

## What shipped

### Lakehouse (PySpark)

- `lakehouse/src/prism_lakehouse` — bronze → silver → gold for Spark `local[*]` and Databricks jobs.
- CLI: `python -m prism_lakehouse --bronze-root … --warehouse-root …`
- Databricks job stub: `lakehouse/jobs/databricks_job_medallion.json` (manual apply, ADR-001).
- Fixture bronze under `lakehouse/fixtures/bronze/` for CI unit tests only.
- Compose: shared `./.data` + `lakehouse` (live) / `lakehouse-fixtures` (synthetic) profiles.

### Expectations & Unity Catalog

- Canonical DQ manifest: `lakehouse/quality/expectations.yaml` (mirrored into package data).
- Expectations → Unity Catalog **table properties** (`quality.expectation.*`) via `unity_catalog/bootstrap.sql`.
- Lakeflow config/notebook reference those property keys; CI validates structurally (no apply).

### dbt Core

- DuckDB CI/local target; `profiles.databricks.yml.example` for real SQL warehouse runs.
- Models + `not_null` / `accepted_range` / `relationships` tests.
- `dbt/docs/dbt-cloud-path.md` (Cloud scheduling / Mesh — no paid account).

## Verified in this environment

| Check | Result |
|-------|--------|
| `make phase2-check` | Green (unit tests include fixture-based Spark test) |
| Live LocalStack ingest → host `./.data/bronze` | Hive `dt=2026-08-02/device=…` files present |
| `docker compose --profile lakehouse run --rm lakehouse` on that bronze | silver 66 / 36, gold 3 / 3 |
| `dbt build --target duckdb` on that warehouse | **PASS=31** |
| Fixture path | Still available for CI; **not** what the live e2e used |

## Deferred

| Item | Lands in |
|------|----------|
| Live Databricks workspace apply of bootstrap / Lakeflow | Manual ops (ADR-001) |
| dbt Cloud account / scheduled Cloud jobs | Documented only |
| CV findings in silver/gold | Phase 3 |
| Activation of gold into Redshift/Snowflake | Phase 4 |

## How to verify (live ingest path)

```bash
# pin backend so lakehouse profile does not recreate ingestion as file
echo 'PRISM_INGEST_BACKEND=localstack' >> .env

PRISM_INGEST_BACKEND=localstack docker compose --profile localstack up -d --build
curl -s http://localhost:9105/health   # backend=localstack, accepted > 0
find .data/bronze -path '*/dt=*/*' | head

docker compose --profile lakehouse run --rm lakehouse
cd dbt && DBT_PROFILES_DIR=$PWD dbt build --target duckdb
```

## Stop

Phase 2 only. Do not start Phase 3 until explicitly requested.
