"""CLI: materialize the PRISM orchestration asset graph in-process."""

from __future__ import annotations

import argparse
import json
import sys

from dagster import materialize

from prism_orchestration.assets import (
    drift_status_snapshot,
    lakehouse_medallion,
    scenario_drift_reseed,
)
from prism_orchestration.config import OrchestrationConfig


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Materialize PRISM Dagster assets")
    parser.add_argument(
        "--select",
        action="append",
        default=[],
        help="Asset name to materialize (repeatable). Default: all three.",
    )
    args = parser.parse_args(argv)
    cfg = OrchestrationConfig.from_env()
    catalog = {
        "lakehouse_medallion": lakehouse_medallion,
        "drift_status_snapshot": drift_status_snapshot,
        "scenario_drift_reseed": scenario_drift_reseed,
    }
    selected = args.select or list(catalog.keys())
    unknown = [n for n in selected if n not in catalog]
    if unknown:
        print(json.dumps({"error": f"unknown assets: {unknown}"}), file=sys.stderr)
        return 2

    assets = [catalog[n] for n in selected]
    result = materialize(assets)
    events = result.get_asset_materialization_events()
    report: dict = {
        "success": result.success,
        "config": {
            "drift_reseed_enabled": cfg.drift_reseed_enabled,
            "bronze_root": str(cfg.bronze_root),
            "warehouse_root": str(cfg.warehouse_root),
            "drift_monitor_url": cfg.drift_monitor_url,
            "scenario_url": cfg.scenario_url,
        },
        "materializations": [],
    }
    for event in events:
        mat = event.materialization
        if mat is None:
            continue
        meta = {k: (v.value if hasattr(v, "value") else v) for k, v in (mat.metadata or {}).items()}
        report["materializations"].append(
            {"asset": mat.asset_key.to_user_string(), "metadata": meta}
        )
    print(json.dumps(report, indent=2, default=str))
    return 0 if result.success else 1


if __name__ == "__main__":
    sys.exit(main())
