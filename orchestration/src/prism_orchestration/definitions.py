"""Dagster Definitions entrypoint: ``dagster dev -m prism_orchestration.definitions``."""

from __future__ import annotations

from dagster import Definitions, define_asset_job

from prism_orchestration.assets import (
    drift_status_snapshot,
    lakehouse_medallion,
    scenario_drift_reseed,
)

all_assets = [
    lakehouse_medallion,
    drift_status_snapshot,
    scenario_drift_reseed,
]

prism_orchestration_job = define_asset_job(
    name="prism_orchestration_job",
    selection=all_assets,
)

defs = Definitions(assets=all_assets, jobs=[prism_orchestration_job])
