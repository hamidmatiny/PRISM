# dbt

dbt Core project modeling silver → gold for PRISM.

| | |
|---|---|
| **CI target** | DuckDB (no cloud) |
| **Prod target** | Databricks SQL warehouse — see `profiles.databricks.yml.example` |
| **dbt Cloud path** | Documented in [`docs/dbt-cloud-path.md`](docs/dbt-cloud-path.md) — not stood up here |

## Prerequisites

1. Run the lakehouse medallion so silver parquet exists under `.data/lakehouse/silver/`.
2. Install: `pip install dbt-core dbt-duckdb`

## Commands

```bash
cd dbt
export DBT_PROFILES_DIR=$PWD
dbt debug --target duckdb
dbt build --target duckdb
dbt docs generate --target duckdb
# docs artifact: target/index.html
```

Or from repo root: `make dbt-build`.

## Models

| Model | Layer | Description |
|-------|-------|-------------|
| `stg_sensor_pings` | silver | Typed sensor pings from Spark parquet / UC |
| `stg_camera_frames` | silver | Camera-frame metadata |
| `dim_assets` | gold | Asset dimension |
| `fct_asset_daily_metrics` | gold | Daily sensor aggregates |
| `fct_fleet_frame_summary` | gold | Daily frame counts |

Tests: `not_null`, custom `accepted_range`, and `relationships` (see `models/schema.yml`).
