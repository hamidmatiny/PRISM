"""Bronze → silver → gold PySpark transforms.

Runnable in Spark local mode and as Databricks jobs (same entrypoints).
Expectation *definitions* live in ``quality/expectations.yaml`` and are applied
as Unity Catalog table properties via bootstrap — transforms enforce the same
predicates locally so laptop runs match UC-gated pipelines.
"""

from __future__ import annotations

from pathlib import Path

from pyspark.sql import DataFrame, SparkSession
from pyspark.sql import functions as F
from pyspark.sql.window import Window

from prism_lakehouse.expectations import load_expectations


def _read_bronze_json(spark: SparkSession, bronze_root: Path, dataset: str) -> DataFrame:
    path = bronze_root / dataset
    if not path.exists():
        return spark.createDataFrame([], schema="asset_id STRING")
    return spark.read.option("multiLine", "true").json(str(path))


def bronze_sensor_pings_to_silver(spark: SparkSession, bronze_root: Path) -> DataFrame:
    raw = _read_bronze_json(spark, bronze_root, "sensor_pings")
    if "timestamp" not in raw.columns:
        return spark.createDataFrame(
            [],
            schema=(
                "asset_id STRING, device_id STRING, event_ts TIMESTAMP, "
                "speed_mph DOUBLE, latitude DOUBLE, longitude DOUBLE, "
                "heading_deg DOUBLE, odometer_km DOUBLE, fuel_level_pct DOUBLE, "
                "schema_version STRING, event_date DATE"
            ),
        )

    typed = raw.select(
        F.col("asset_id").cast("string").alias("asset_id"),
        F.col("device_id").cast("string").alias("device_id"),
        F.to_timestamp("timestamp").alias("event_ts"),
        F.col("speed_mph").cast("double").alias("speed_mph"),
        F.col("latitude").cast("double").alias("latitude"),
        F.col("longitude").cast("double").alias("longitude"),
        F.col("heading_deg").cast("double").alias("heading_deg"),
        F.col("odometer_km").cast("double").alias("odometer_km"),
        F.col("fuel_level_pct").cast("double").alias("fuel_level_pct"),
        F.col("schema_version").cast("string").alias("schema_version"),
    ).withColumn("event_date", F.to_date("event_ts"))
    return _apply_silver_sensor_expectations(typed)


def bronze_camera_frames_to_silver(spark: SparkSession, bronze_root: Path) -> DataFrame:
    raw = _read_bronze_json(spark, bronze_root, "camera_frames")
    if "timestamp" not in raw.columns:
        return spark.createDataFrame(
            [],
            schema=(
                "asset_id STRING, device_id STRING, frame_id STRING, event_ts TIMESTAMP, "
                "storage_uri STRING, content_type STRING, width_px INT, height_px INT, "
                "capture_exposure_ms DOUBLE, schema_version STRING, event_date DATE"
            ),
        )

    typed = raw.select(
        F.col("asset_id").cast("string").alias("asset_id"),
        F.col("device_id").cast("string").alias("device_id"),
        F.col("frame_id").cast("string").alias("frame_id"),
        F.to_timestamp("timestamp").alias("event_ts"),
        F.col("storage_uri").cast("string").alias("storage_uri"),
        F.col("content_type").cast("string").alias("content_type"),
        F.col("width_px").cast("int").alias("width_px"),
        F.col("height_px").cast("int").alias("height_px"),
        F.col("capture_exposure_ms").cast("double").alias("capture_exposure_ms"),
        F.col("schema_version").cast("string").alias("schema_version"),
    ).withColumn("event_date", F.to_date("event_ts"))
    return _apply_silver_camera_expectations(typed)


def _apply_silver_sensor_expectations(df: DataFrame) -> DataFrame:
    """Enforce predicates from expectations.yaml (local parity with UC props)."""
    expectations = load_expectations()["tables"]["silver.sensor_pings"]["expectations"]
    filtered = df.filter(
        F.col("asset_id").isNotNull()
        & F.col("device_id").isNotNull()
        & F.col("event_ts").isNotNull()
    )
    # Map named expectations to Spark filters for drop-action rules.
    for item in expectations:
        if item.get("action") != "drop":
            continue
        name = item["name"]
        if name == "speed_range":
            filtered = filtered.filter(F.col("speed_mph").between(0, 120))
        elif name == "latitude_range":
            filtered = filtered.filter(F.col("latitude").between(-90, 90))
        elif name == "longitude_range":
            filtered = filtered.filter(F.col("longitude").between(-180, 180))
        elif name == "asset_id_pattern":
            filtered = filtered.filter(F.col("asset_id").rlike(r"^PRISM-AST-\d{3}$"))

    window = Window.partitionBy("asset_id", "device_id", "event_ts").orderBy(F.col("event_ts"))
    return (
        filtered.withColumn("_rn", F.row_number().over(window))
        .filter(F.col("_rn") == 1)
        .drop("_rn")
    )


def _apply_silver_camera_expectations(df: DataFrame) -> DataFrame:
    expectations = load_expectations()["tables"]["silver.camera_frames"]["expectations"]
    filtered = df.filter(
        F.col("asset_id").isNotNull()
        & F.col("frame_id").isNotNull()
        & F.col("event_ts").isNotNull()
    )
    for item in expectations:
        if item.get("action") != "drop":
            continue
        name = item["name"]
        if name == "width_positive":
            filtered = filtered.filter(F.col("width_px") >= 1)
        elif name == "height_positive":
            filtered = filtered.filter(F.col("height_px") >= 1)
        elif name == "storage_uri_scheme":
            filtered = filtered.filter(F.col("storage_uri").rlike(r"^(s3|file)://"))

    window = Window.partitionBy("frame_id").orderBy(F.col("event_ts"))
    return (
        filtered.withColumn("_rn", F.row_number().over(window))
        .filter(F.col("_rn") == 1)
        .drop("_rn")
    )


def silver_to_gold_asset_daily(sensor_silver: DataFrame) -> DataFrame:
    return (
        sensor_silver.groupBy("asset_id", F.col("event_date").alias("metric_date"))
        .agg(
            F.count("*").alias("ping_count"),
            F.avg("speed_mph").alias("avg_speed_mph"),
            F.max("speed_mph").alias("max_speed_mph"),
            F.avg("fuel_level_pct").alias("avg_fuel_level_pct"),
            F.max("odometer_km").alias("max_odometer_km"),
            F.min("event_ts").alias("first_event_ts"),
            F.max("event_ts").alias("last_event_ts"),
        )
        .filter(F.col("ping_count") >= 0)
    )


def silver_to_gold_frame_summary(camera_silver: DataFrame) -> DataFrame:
    return (
        camera_silver.groupBy("asset_id", F.col("event_date").alias("metric_date"))
        .agg(
            F.count("*").alias("frame_count"),
            F.countDistinct("device_id").alias("camera_device_count"),
            F.min("event_ts").alias("first_frame_ts"),
            F.max("event_ts").alias("last_frame_ts"),
        )
        .filter(F.col("frame_count") >= 0)
    )


def run_medallion(
    spark: SparkSession,
    *,
    bronze_root: Path,
    warehouse_root: Path,
) -> dict[str, int]:
    """Execute bronze→silver→gold and write parquet datasets. Returns row counts."""
    silver_root = warehouse_root / "silver"
    gold_root = warehouse_root / "gold"
    silver_root.mkdir(parents=True, exist_ok=True)
    gold_root.mkdir(parents=True, exist_ok=True)

    sensor_silver = bronze_sensor_pings_to_silver(spark, bronze_root)
    camera_silver = bronze_camera_frames_to_silver(spark, bronze_root)

    sensor_path = silver_root / "sensor_pings"
    camera_path = silver_root / "camera_frames"
    (sensor_silver.write.mode("overwrite").partitionBy("event_date").parquet(str(sensor_path)))
    (camera_silver.write.mode("overwrite").partitionBy("event_date").parquet(str(camera_path)))

    asset_daily = silver_to_gold_asset_daily(sensor_silver)
    frame_summary = silver_to_gold_frame_summary(camera_silver)
    asset_path = gold_root / "asset_daily_metrics"
    frame_path = gold_root / "fleet_frame_summary"
    (asset_daily.write.mode("overwrite").partitionBy("metric_date").parquet(str(asset_path)))
    (frame_summary.write.mode("overwrite").partitionBy("metric_date").parquet(str(frame_path)))

    return {
        "silver.sensor_pings": sensor_silver.count(),
        "silver.camera_frames": camera_silver.count(),
        "gold.asset_daily_metrics": asset_daily.count(),
        "gold.fleet_frame_summary": frame_summary.count(),
    }
