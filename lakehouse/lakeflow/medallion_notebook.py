# Databricks notebook source (`.py` format) for Lakeflow Declarative Pipeline.
# Deploy manually to /Repos/prism/lakeflow/medallion_notebook — CI only
# validates structure (ADR-001).

# COMMAND ----------
# MAGIC %md
# MAGIC # PRISM medallion (Lakeflow)
# MAGIC Expectations are read from Unity Catalog table properties set by
# MAGIC `lakehouse/unity_catalog/bootstrap.sql` (generated from
# MAGIC `lakehouse/quality/expectations.yaml`).

# COMMAND ----------

from pyspark import pipelines as dp
from pyspark.sql import functions as F

# COMMAND ----------


@dp.table(name="silver.sensor_pings", comment="Typed sensor pings")
@dp.expect_all_or_drop(
    {
        "speed_range": "speed_mph BETWEEN 0 AND 120",
        "latitude_range": "latitude BETWEEN -90 AND 90",
        "longitude_range": "longitude BETWEEN -180 AND 180",
        "asset_id_pattern": "asset_id RLIKE '^PRISM-AST-[0-9]{3}$'",
    }
)
@dp.expect_all(
    {
        "asset_id_not_null": "asset_id IS NOT NULL",
        "device_id_not_null": "device_id IS NOT NULL",
        "timestamp_not_null": "event_ts IS NOT NULL",
    }
)
def silver_sensor_pings():
    # In workspace: read bronze volume. Keys above MUST match UC TBLPROPERTIES
    # from expectations.yaml (validated in CI by validate_bootstrap.py).
    return (
        spark.read.format("json")
        .load("/Volumes/prism/bronze/raw/sensor_pings")
        .select(
            F.col("asset_id"),
            F.col("device_id"),
            F.to_timestamp("timestamp").alias("event_ts"),
            F.col("speed_mph").cast("double"),
            F.col("latitude").cast("double"),
            F.col("longitude").cast("double"),
            F.col("heading_deg").cast("double"),
            F.col("odometer_km").cast("double"),
            F.col("fuel_level_pct").cast("double"),
            F.col("schema_version"),
        )
        .withColumn("event_date", F.to_date("event_ts"))
    )


# COMMAND ----------


@dp.table(name="silver.camera_frames", comment="Typed camera-frame metadata")
@dp.expect_all_or_drop(
    {
        "width_positive": "width_px >= 1",
        "height_positive": "height_px >= 1",
        "storage_uri_scheme": "storage_uri RLIKE '^(s3|file)://'",
    }
)
@dp.expect_all(
    {
        "asset_id_not_null": "asset_id IS NOT NULL",
        "frame_id_not_null": "frame_id IS NOT NULL",
        "timestamp_not_null": "event_ts IS NOT NULL",
    }
)
def silver_camera_frames():
    return (
        spark.read.format("json")
        .load("/Volumes/prism/bronze/raw/camera_frames")
        .select(
            F.col("asset_id"),
            F.col("device_id"),
            F.col("frame_id"),
            F.to_timestamp("timestamp").alias("event_ts"),
            F.col("storage_uri"),
            F.col("content_type"),
            F.col("width_px").cast("int"),
            F.col("height_px").cast("int"),
            F.col("capture_exposure_ms").cast("double"),
            F.col("schema_version"),
        )
        .withColumn("event_date", F.to_date("event_ts"))
    )


# COMMAND ----------


@dp.table(name="gold.asset_daily_metrics", comment="Per-asset daily sensor aggregates")
@dp.expect_all(
    {
        "asset_id_not_null": "asset_id IS NOT NULL",
        "metric_date_not_null": "metric_date IS NOT NULL",
        "ping_count_positive": "ping_count >= 0",
    }
)
@dp.expect_or_drop(
    "avg_speed_range",
    "avg_speed_mph IS NULL OR (avg_speed_mph BETWEEN 0 AND 120)",
)
def gold_asset_daily_metrics():
    return (
        spark.read.table("silver.sensor_pings")
        .groupBy("asset_id", F.col("event_date").alias("metric_date"))
        .agg(
            F.count("*").alias("ping_count"),
            F.avg("speed_mph").alias("avg_speed_mph"),
            F.max("speed_mph").alias("max_speed_mph"),
            F.avg("fuel_level_pct").alias("avg_fuel_level_pct"),
            F.max("odometer_km").alias("max_odometer_km"),
            F.min("event_ts").alias("first_event_ts"),
            F.max("event_ts").alias("last_event_ts"),
        )
    )


# COMMAND ----------


@dp.table(name="gold.fleet_frame_summary", comment="Per-asset daily frame counts")
@dp.expect_all(
    {
        "asset_id_not_null": "asset_id IS NOT NULL",
        "metric_date_not_null": "metric_date IS NOT NULL",
        "frame_count_nonneg": "frame_count >= 0",
    }
)
def gold_fleet_frame_summary():
    return (
        spark.read.table("silver.camera_frames")
        .groupBy("asset_id", F.col("event_date").alias("metric_date"))
        .agg(
            F.count("*").alias("frame_count"),
            F.countDistinct("device_id").alias("camera_device_count"),
            F.min("event_ts").alias("first_frame_ts"),
            F.max("event_ts").alias("last_frame_ts"),
        )
    )
