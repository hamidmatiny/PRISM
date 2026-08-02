# dbt Cloud path (documented, not provisioned)

This repository runs **dbt Core** against DuckDB in CI and locally. A paid dbt Cloud account is **not** stood up in this build (ADR-001 / cost-safety). This document explains how the same project would be scheduled in dbt Cloud for production Databricks SQL warehouse runs.

## Why Core first

| Concern | Choice |
|---------|--------|
| CI cost | DuckDB + Core — no cloud warehouse |
| Portability | Same `models/` and tests run locally and in Cloud |
| Governance | Unity Catalog remains the warehouse catalog; dbt is the transform/test layer on silver→gold |

## Environments

Map dbt Cloud environments to PRISM stages:

| dbt Cloud env | dbt target | Warehouse | Purpose |
|---------------|------------|-----------|---------|
| CI / develop | `duckdb` | Local file | PR checks (what this repo runs today) |
| staging | `databricks` | Databricks SQL warehouse (non-prod) | Pre-prod validation against UC `prism` staging schemas |
| production | `databricks` | Databricks SQL warehouse (prod) | Scheduled gold materialization |

Connection details for Databricks come from dbt Cloud deployment credentials (host, HTTP path, token/service principal) — never committed. See `profiles.databricks.yml.example`.

## Job scheduling

Suggested Cloud jobs (cron in workspace timezone):

1. **`prism-silver-refresh-deps`** (optional) — if Lakeflow / Spark jobs own silver, this job only waits on an upstream success signal (Databricks job completion webhook or warehouse freshness check).
2. **`prism-dbt-build-staging`** — `dbt build --target databricks` on staging after medallion completes; runs models + tests.
3. **`prism-dbt-build-prod`** — same command on production; blocked on green staging or a required approval in Cloud.
4. **`prism-dbt-docs`** — `dbt docs generate` nightly; publish the docs artifact to the Cloud docs site or static hosting.

Slim CI in GitHub Actions should keep using DuckDB; Cloud jobs are the Databricks path.

## Project structure vs dbt Mesh

Today this is a **single dbt project** (`name: prism`) with `silver/` and `gold/` model directories. That is enough while one team owns the medallion.

If ownership splits later, consider **dbt Mesh** / multi-project:

| Project | Owns | Exposes |
|---------|------|---------|
| `prism_silver` | Staging models over UC silver | Public models for sensor pings / frames |
| `prism_gold` | Marts / facts / dims | Public contracts for activation-gateway & cockpit |
| `prism_metrics` (optional) | Reverse-ETL / serving-oriented marts | Warehouse-agnostic activation inputs |

Cross-project refs would use `{{ ref('prism_silver', 'stg_sensor_pings') }}` (Mesh model governance) with clear owner + SLAs. Do **not** split prematurely — Mesh adds coordination cost; wait until separate teams or release cadences actually diverge.

## Fusion / Cloud upgrade notes

- Stay on **dbt Core** semantics in-repo so local DuckDB CI remains valid.
- If adopting dbt Cloud + Fusion later, keep model SQL standard and avoid adapter-specific logic outside the `silver_relation` macro (already the single branch point for DuckDB parquet vs UC tables).
- Document any Cloud-only features (CI job in Cloud, explorer, Semantic Layer) as optional overlays — they must not become required to run `make dbt-build` on a laptop.

## Explicit non-goals for this build

- No dbt Cloud account, trial, or paid seat
- No live Databricks SQL warehouse connection in CI
- No Mesh multi-project split until a real ownership boundary appears
