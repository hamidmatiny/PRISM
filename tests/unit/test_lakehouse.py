"""Lakehouse expectations, UC bootstrap validation, and Spark medallion tests."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
FIXTURE_BRONZE = ROOT / "lakehouse" / "fixtures" / "bronze"


def test_expectations_manifest_loads() -> None:
    from prism_lakehouse.expectations import all_table_keys, table_properties_for

    keys = all_table_keys()
    assert "silver.sensor_pings" in keys
    assert "gold.asset_daily_metrics" in keys
    props = table_properties_for("silver.sensor_pings")
    assert props["quality.expectation.speed_range"] == "speed_mph BETWEEN 0 AND 120"
    assert props["quality.expectation.speed_range.action"] == "drop"


def test_packaged_expectations_match_repo_copy() -> None:
    repo = (ROOT / "lakehouse" / "quality" / "expectations.yaml").read_text(encoding="utf-8")
    pkg = (ROOT / "lakehouse" / "src" / "prism_lakehouse" / "data" / "expectations.yaml").read_text(
        encoding="utf-8"
    )
    assert repo == pkg


def test_bootstrap_sql_is_current_and_valid() -> None:
    render = ROOT / "lakehouse" / "unity_catalog" / "render_bootstrap.py"
    validate = ROOT / "lakehouse" / "unity_catalog" / "validate_bootstrap.py"
    assert subprocess.run([sys.executable, str(render), "--check"], check=False).returncode == 0
    assert subprocess.run([sys.executable, str(validate)], check=False).returncode == 0


def test_medallion_local_spark(tmp_path: Path) -> None:
    pyspark = pytest.importorskip("pyspark")
    del pyspark
    from prism_lakehouse.spark_session import build_local_spark
    from prism_lakehouse.transforms import run_medallion

    out = tmp_path / "warehouse"
    spark = build_local_spark("prism-test")
    try:
        counts = run_medallion(spark, bronze_root=FIXTURE_BRONZE, warehouse_root=out)
    finally:
        spark.stop()

    assert counts["silver.sensor_pings"] == 3
    assert counts["silver.camera_frames"] == 2
    assert counts["gold.asset_daily_metrics"] >= 1
    assert counts["gold.fleet_frame_summary"] >= 1
    assert list((out / "silver" / "sensor_pings").rglob("*.parquet"))
    assert list((out / "gold" / "asset_daily_metrics").rglob("*.parquet"))


def test_databricks_job_json_is_parseable() -> None:
    job = json.loads(
        (ROOT / "lakehouse" / "jobs" / "databricks_job_medallion.json").read_text(encoding="utf-8")
    )
    assert job["tasks"][0]["task_key"] == "run_medallion"
    assert job["tags"]["cost_safety"] == "manual-apply-only"
