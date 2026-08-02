# lakehouse

PySpark bronze → silver → gold medallion transforms, Lakeflow Declarative Pipeline
defs, and Unity Catalog bootstrap.

| | |
|---|---|
| **Port** | N/A (batch job) |
| **Local** | `python -m prism_lakehouse` (Spark `local[*]`) |
| **Docker (live bronze)** | `docker compose --profile lakehouse run --rm lakehouse` — reads `./.data/bronze` written by ingestion |
| **Docker (fixtures only)** | `docker compose --profile lakehouse run --rm lakehouse-fixtures` — CI/offline; not the ingest path |
| **Databricks** | `jobs/databricks_job_medallion.json` + `lakeflow/` (manual apply, ADR-001) |

**Data path contract:** host `./.data` is bind-mounted as `/data` for both `ingestion` and `lakehouse`. Do not assume a Docker named volume holds bronze separately from the host.

## Layout

```
lakehouse/
├── quality/expectations.yaml      # canonical DQ expectations (UC table props)
├── unity_catalog/bootstrap.sql    # generated; apply manually
├── unity_catalog/validate_bootstrap.py
├── lakeflow/prism_medallion.yml   # Lakeflow pipeline — refs UC property keys
├── lakeflow/medallion_notebook.py
├── jobs/databricks_job_medallion.json
├── fixtures/bronze/               # sample Hive bronze for CI / local
└── src/prism_lakehouse/           # Spark transforms
```

## Run locally

```bash
export JAVA_HOME=/opt/homebrew/opt/openjdk@21
export PATH="$JAVA_HOME/bin:$PATH"
pip install -e lakehouse
python -m prism_lakehouse \
  --bronze-root lakehouse/fixtures/bronze \
  --warehouse-root .data/lakehouse
```

Expectations are loaded from `quality/expectations.yaml` and enforced in the
local transforms for parity with Unity Catalog `quality.expectation.*`
table properties applied by `unity_catalog/bootstrap.sql`.
