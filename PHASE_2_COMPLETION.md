# Phase 2 completion — Lakehouse core

**Date:** 2026-08-01  
**Status:** Complete (awaiting human go-ahead before Phase 3)

## What shipped

### Lakehouse (PySpark)

- `lakehouse/src/prism_lakehouse` — bronze → silver → gold transforms for Spark `local[*]` and Databricks jobs.
- CLI: `python -m prism_lakehouse --bronze-root … --warehouse-root …`
- Databricks job stub: `lakehouse/jobs/databricks_job_medallion.json` (manual apply, ADR-001).
- Fixture bronze under `lakehouse/fixtures/bronze/` for CI / local runs.
- Docker image + compose profile `lakehouse` (`lakehouse-fixtures` one-shot).

### Expectations & Unity Catalog

- Canonical DQ manifest: `lakehouse/quality/expectations.yaml` (mirrored into package data).
- Expectations projected to Unity Catalog **table properties** (`quality.expectation.*`) via generated `lakehouse/unity_catalog/bootstrap.sql`.
- Lakeflow Declarative Pipeline config `lakeflow/prism_medallion.yml` + notebook reference property keys (validated in CI — no apply).
- `validate_bootstrap.py` structurally checks bootstrap SQL, grants, Lakeflow key parity, job cost-safety tag.

### dbt Core

- Project under `dbt/` with DuckDB target for CI/local and `profiles.databricks.yml.example` for real SQL warehouse runs.
- Models: `stg_sensor_pings`, `stg_camera_frames`, `dim_assets`, `fct_asset_daily_metrics`, `fct_fleet_frame_summary`.
- Tests: `not_null`, custom `accepted_range`, `relationships`.
- `dbt docs generate` produces `dbt/target/` catalog.
- `dbt/docs/dbt-cloud-path.md` documents Cloud environments, scheduling, and Mesh considerations (no paid Cloud account).

## Verified in this environment

| Check | Result |
|-------|--------|
| `make phase2-check` (lint + unit tests + UC validate + terraform validate) | Green |
| Local Spark medallion on fixtures | `silver.sensor_pings=3`, `camera_frames=2`, gold rows written |
| `dbt build --target duckdb` | **PASS=31** (5 models + 26 tests) |
| `dbt docs generate` | `dbt/target/catalog.json` written |
| `docker compose --profile lakehouse run --rm --build lakehouse-fixtures` | `status=ok` counts silver 3/2, gold 2/2 |

## Deferred

| Item | Lands in |
|------|----------|
| Live Databricks workspace apply of bootstrap / Lakeflow | Manual ops (ADR-001) |
| dbt Cloud account / scheduled Cloud jobs | Documented only |
| CV findings in silver/gold | Phase 3 |
| Activation of gold into Redshift/Snowflake | Phase 4 |

## How to verify

```bash
export JAVA_HOME=/opt/homebrew/opt/openjdk@21   # or system JDK 17+
export PATH="$JAVA_HOME/bin:$PATH"
pip install -e lakehouse 'dbt-core>=1.8' 'dbt-duckdb>=1.8'
make phase2-check
make lakehouse-run
make dbt-build
docker compose --profile lakehouse run --rm --build lakehouse-fixtures
```

## Stop

Phase 2 only. Do not start Phase 3 until explicitly requested.
