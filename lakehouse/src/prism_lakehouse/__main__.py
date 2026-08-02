"""CLI: ``python -m prism_lakehouse`` — local Spark medallion run."""

from __future__ import annotations

import argparse
import json
import logging
import sys
from pathlib import Path

from prism_lakehouse.spark_session import get_spark
from prism_lakehouse.transforms import run_medallion


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="PRISM lakehouse medallion transforms")
    parser.add_argument(
        "--bronze-root",
        type=Path,
        default=Path(".data/bronze"),
        help="Hive-partitioned bronze JSON root from ingestion.",
    )
    parser.add_argument(
        "--warehouse-root",
        type=Path,
        default=Path(".data/lakehouse"),
        help="Output root for silver/ and gold/ parquet datasets.",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )
    args = _build_parser().parse_args(argv)
    spark = get_spark()
    try:
        counts = run_medallion(
            spark,
            bronze_root=args.bronze_root,
            warehouse_root=args.warehouse_root,
        )
    finally:
        spark.stop()
    logging.getLogger(__name__).info("Medallion complete: %s", json.dumps(counts))
    print(json.dumps({"status": "ok", "counts": counts}, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
