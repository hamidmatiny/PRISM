"""Render Unity Catalog bootstrap SQL from quality/expectations.yaml."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from prism_lakehouse.expectations import (  # noqa: E402
    PROPERTY_PREFIX,
    load_expectations,
    table_properties_for,
)

OUT_PATH = Path(__file__).resolve().parent / "bootstrap.sql"


def render_sql(path: Path | None = None) -> str:
    data = load_expectations(path)
    catalog = data["catalog"]
    lines = [
        "-- PRISM Unity Catalog bootstrap",
        "-- GENERATED from lakehouse/quality/expectations.yaml — do not hand-edit.",
        "-- Regenerate: python lakehouse/unity_catalog/render_bootstrap.py",
        "-- Apply manually against a real Databricks workspace (ADR-001). Never from CI.",
        "",
        f"CREATE CATALOG IF NOT EXISTS {catalog};",
        f"USE CATALOG {catalog};",
        "",
    ]
    for schema in data["schemas"]:
        lines.append(f"CREATE SCHEMA IF NOT EXISTS {catalog}.{schema};")
    lines.append("")

    # Placeholder managed tables so TBLPROPERTIES can be set before Lakeflow owns them.
    ddl = {
        "silver.sensor_pings": """
CREATE TABLE IF NOT EXISTS {catalog}.silver.sensor_pings (
  asset_id STRING,
  device_id STRING,
  event_ts TIMESTAMP,
  speed_mph DOUBLE,
  latitude DOUBLE,
  longitude DOUBLE,
  heading_deg DOUBLE,
  odometer_km DOUBLE,
  fuel_level_pct DOUBLE,
  schema_version STRING,
  event_date DATE
) USING DELTA;
""".strip(),
        "silver.camera_frames": """
CREATE TABLE IF NOT EXISTS {catalog}.silver.camera_frames (
  asset_id STRING,
  device_id STRING,
  frame_id STRING,
  event_ts TIMESTAMP,
  storage_uri STRING,
  content_type STRING,
  width_px INT,
  height_px INT,
  capture_exposure_ms DOUBLE,
  schema_version STRING,
  event_date DATE
) USING DELTA;
""".strip(),
        "gold.asset_daily_metrics": """
CREATE TABLE IF NOT EXISTS {catalog}.gold.asset_daily_metrics (
  asset_id STRING,
  metric_date DATE,
  ping_count BIGINT,
  avg_speed_mph DOUBLE,
  max_speed_mph DOUBLE,
  avg_fuel_level_pct DOUBLE,
  max_odometer_km DOUBLE,
  first_event_ts TIMESTAMP,
  last_event_ts TIMESTAMP
) USING DELTA;
""".strip(),
        "gold.fleet_frame_summary": """
CREATE TABLE IF NOT EXISTS {catalog}.gold.fleet_frame_summary (
  asset_id STRING,
  metric_date DATE,
  frame_count BIGINT,
  camera_device_count BIGINT,
  first_frame_ts TIMESTAMP,
  last_frame_ts TIMESTAMP
) USING DELTA;
""".strip(),
    }

    for table_key, template in ddl.items():
        schema_name, table_name = table_key.split(".", 1)
        comment = data["tables"][table_key].get("comment", "")
        lines.append(template.format(catalog=catalog))
        lines.append(f"COMMENT ON TABLE {catalog}.{schema_name}.{table_name} IS '{comment}';")
        props = table_properties_for(table_key, path)

        def _esc(value: str) -> str:
            return value.replace("'", "''")

        prop_sql = ",\n  ".join(f"'{k}' = '{_esc(v)}'" for k, v in props.items())
        fq_table = f"{catalog}.{schema_name}.{table_name}"
        lines.append(f"ALTER TABLE {fq_table} SET TBLPROPERTIES (\n  {prop_sql}\n);")
        lines.append("")

    # Grants — structurally present; principals are placeholders for real IdP groups.
    lines.extend(
        [
            f"GRANT USE CATALOG ON CATALOG {catalog} TO `account users`;",
            f"GRANT USE SCHEMA ON SCHEMA {catalog}.bronze TO `account users`;",
            f"GRANT USE SCHEMA ON SCHEMA {catalog}.silver TO `account users`;",
            f"GRANT USE SCHEMA ON SCHEMA {catalog}.gold TO `account users`;",
            f"GRANT SELECT ON SCHEMA {catalog}.gold TO `prism-viewers`;",
            f"GRANT SELECT, MODIFY ON SCHEMA {catalog}.silver TO `prism-engineers`;",
            f"GRANT ALL PRIVILEGES ON CATALOG {catalog} TO `prism-admins`;",
            "",
            f"-- Expectation property prefix in use: {PROPERTY_PREFIX}",
        ]
    )
    return "\n".join(lines) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true", help="Exit 1 if bootstrap.sql is stale")
    args = parser.parse_args()
    sql = render_sql()
    if args.check:
        if not OUT_PATH.is_file() or OUT_PATH.read_text(encoding="utf-8") != sql:
            print("bootstrap.sql is stale; run render_bootstrap.py", file=sys.stderr)
            return 1
        print("bootstrap.sql is up to date")
        return 0
    OUT_PATH.write_text(sql, encoding="utf-8")
    print(f"wrote {OUT_PATH}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
