"""Env-driven orchestration settings (ADR-001 local-first)."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


def _truthy(raw: str | None) -> bool:
    if raw is None or raw == "":
        return False
    return raw.strip().lower() in {"1", "true", "yes", "on"}


def _int_env(name: str, default: int) -> int:
    raw = os.getenv(name)
    if raw is None or raw == "":
        return default
    return int(raw)


@dataclass(frozen=True)
class OrchestrationConfig:
    bronze_root: Path = Path("lakehouse/fixtures/bronze")
    warehouse_root: Path = Path(".data/lakehouse-from-orchestration")
    drift_monitor_url: str = "http://127.0.0.1:9109"
    scenario_url: str = "http://127.0.0.1:9107"
    drift_reseed_enabled: bool = False
    reseed_seed: int = 17
    reseed_ticks: int = 5
    reseed_scenario_id_prefix: str = "scn_drift_reseed"
    http_timeout_s: float = 10.0
    port: int = 9112

    @classmethod
    def from_env(cls) -> OrchestrationConfig:
        return cls(
            bronze_root=Path(os.getenv("PRISM_ORCH_BRONZE_ROOT", "lakehouse/fixtures/bronze")),
            warehouse_root=Path(
                os.getenv("PRISM_ORCH_WAREHOUSE_ROOT", ".data/lakehouse-from-orchestration")
            ),
            drift_monitor_url=os.getenv("PRISM_DRIFT_MONITOR_URL", "http://127.0.0.1:9109").rstrip(
                "/"
            ),
            scenario_url=os.getenv("PRISM_SCENARIO_URL", "http://127.0.0.1:9107").rstrip("/"),
            drift_reseed_enabled=_truthy(os.getenv("PRISM_DAGSTER_DRIFT_RESEED")),
            reseed_seed=_int_env("PRISM_ORCH_RESEED_SEED", 17),
            reseed_ticks=_int_env("PRISM_ORCH_RESEED_TICKS", 5),
            reseed_scenario_id_prefix=os.getenv("PRISM_ORCH_RESEED_ID_PREFIX", "scn_drift_reseed"),
            http_timeout_s=float(os.getenv("PRISM_ORCH_HTTP_TIMEOUT", "10")),
            port=_int_env("PRISM_ORCH_PORT", 9112),
        )
