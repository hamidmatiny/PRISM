{% docs __overview__ %}
# PRISM dbt project

Silver → gold modeling on top of the Spark / Lakeflow medallion.

- **CI / local:** DuckDB reading parquet from `prism_lakehouse`
- **Production path:** Databricks SQL warehouse (see `profiles.databricks.yml.example` and `docs/dbt-cloud-path.md`)
- **Quality:** `not_null`, `accepted_range`, and `relationships` tests in `models/schema.yml`

Expectations at the lakehouse layer are also stored as Unity Catalog table properties
(`lakehouse/quality/expectations.yaml`).
{% enddocs %}
