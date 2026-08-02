"""Runtime configuration for scenario-engine."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


def _int_env(name: str, default: int) -> int:
    raw = os.getenv(name)
    if raw is None or raw == "":
        return default
    return int(raw)


@dataclass(frozen=True)
class ScenarioConfig:
    data_root: Path = Path(".data")
    seed: int = 42
    scenario_id: str = ""
    asset_ids: tuple[str, ...] = ("PRISM-AST-001", "PRISM-AST-002", "PRISM-AST-003")
    weights_path: Path | None = None
    port: int = 9107
    host: str = "0.0.0.0"

    @property
    def journal_dir(self) -> Path:
        return self.data_root / "scenario" / "journal"

    @classmethod
    def from_env(cls) -> ScenarioConfig:
        assets_raw = os.getenv("PRISM_ASSET_IDS", "PRISM-AST-001,PRISM-AST-002,PRISM-AST-003")
        asset_ids = tuple(a.strip() for a in assets_raw.split(",") if a.strip())
        seed = _int_env("PRISM_SCENARIO_SEED", 42)
        scenario_id = os.getenv("PRISM_SCENARIO_ID", "").strip() or f"scn_{seed}"
        weights = os.getenv("PRISM_SCENARIO_WEIGHTS", "").strip()
        return cls(
            data_root=Path(os.getenv("PRISM_DATA_ROOT", ".data")),
            seed=seed,
            scenario_id=scenario_id,
            asset_ids=asset_ids or ("PRISM-AST-001",),
            weights_path=Path(weights) if weights else None,
            port=_int_env("PRISM_SCENARIO_PORT", 9107),
            host=os.getenv("PRISM_HEALTH_HOST", "0.0.0.0"),
        )
