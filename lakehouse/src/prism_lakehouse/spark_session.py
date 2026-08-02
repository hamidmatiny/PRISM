"""Spark session builders for local mode and Databricks (existing session)."""

from __future__ import annotations

from pyspark.sql import SparkSession


def build_local_spark(app_name: str = "prism-lakehouse") -> SparkSession:
    """Spark local[*] — no cluster / cloud credentials (ADR-001)."""
    return (
        SparkSession.builder.appName(app_name)
        .master("local[*]")
        .config("spark.sql.shuffle.partitions", "4")
        .config("spark.ui.enabled", "false")
        .config("spark.driver.host", "127.0.0.1")
        .config("spark.sql.session.timeZone", "UTC")
        .getOrCreate()
    )


def get_spark(app_name: str = "prism-lakehouse") -> SparkSession:
    """Reuse an active session (Databricks job) or create a local one."""
    existing = SparkSession.getActiveSession()
    if existing is not None:
        return existing
    return build_local_spark(app_name)
