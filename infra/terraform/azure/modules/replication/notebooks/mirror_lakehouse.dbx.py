# Databricks notebook source (import under /Repos/prism/azure_dr/mirror_lakehouse).
# Warm-standby mirror: AWS S3 lakehouse zones → ADLS Gen2.
# Cadence / RPO is owned by the Jobs schedule (default every 15 minutes).
#
# Widgets (base_parameters from the job definition):
#   aws_gold_uri, aws_raw_uri, adls_gold_uri, adls_bronze_uri, adls_silver_uri, rpo_minutes

# COMMAND ----------

dbutils.widgets.text("aws_gold_uri", "")
dbutils.widgets.text("aws_raw_uri", "")
dbutils.widgets.text("adls_gold_uri", "")
dbutils.widgets.text("adls_bronze_uri", "")
dbutils.widgets.text("adls_silver_uri", "")
dbutils.widgets.text("rpo_minutes", "15")

aws_gold = dbutils.widgets.get("aws_gold_uri")
aws_raw = dbutils.widgets.get("aws_raw_uri")
adls_gold = dbutils.widgets.get("adls_gold_uri")
adls_bronze = dbutils.widgets.get("adls_bronze_uri")
adls_silver = dbutils.widgets.get("adls_silver_uri")
rpo = int(dbutils.widgets.get("rpo_minutes"))

# COMMAND ----------

# Credentials: use instance profile / Unity Catalog storage credentials configured
# at human apply time. This notebook assumes s3a:// and abfss:// are already
# authorized for the job cluster identity — no secrets in source.


def mirror_prefix(src: str, dst: str, label: str) -> None:
    if not src or not dst:
        print(f"skip {label}: empty uri")
        return
    print(f"mirroring {label}: {src} -> {dst}")
    (
        spark.read.format("binaryFile")
        .option("pathGlobFilter", "*")
        .option("recursiveFileLookup", "true")
        .load(src)
        .write.mode("overwrite")
        .format("binaryFile")
        .save(dst.rstrip("/") + "/_mirror_staging")
    )
    # Production apply replaces binaryFile staging with dbutils.fs.cp recursive
    # or Delta CLONE when source tables are Delta. Staging path proves the wire.


mirror_prefix(aws_gold, adls_gold, "gold")
mirror_prefix(aws_raw, adls_bronze, "bronze")
# Silver is derived in AWS; optional second-hop mirror when present on S3.
# mirror_prefix(aws_silver, adls_silver, "silver")

print(f"mirror complete; RPO target minutes={rpo}")
