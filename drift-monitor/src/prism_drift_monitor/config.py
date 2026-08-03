"""Runtime configuration for drift-monitor (local-first, ADR-001)."""

from __future__ import annotations

import os
from dataclasses import dataclass


def _float_env(name: str, default: float) -> float:
    raw = os.getenv(name)
    if raw is None or raw == "":
        return default
    return float(raw)


def _int_env(name: str, default: int) -> int:
    raw = os.getenv(name)
    if raw is None or raw == "":
        return default
    return int(raw)


@dataclass(frozen=True)
class DriftConfig:
    host: str = "0.0.0.0"
    port: int = 9109
    incident_engine_url: str = "http://127.0.0.1:9108"
    # Real, non-synthetic samples required before a (asset_id, group)
    # baseline freezes and detection goes live (ADR-005).
    baseline_samples: int = 20
    # Rolling comparison-window size; a fresh detection run fires on every
    # new sample once the window is full.
    window_size: int = 10
    ks_alpha: float = 0.05
    centroid_z: float = 2.5

    @classmethod
    def from_env(cls) -> DriftConfig:
        return cls(
            host=os.getenv("PRISM_HEALTH_HOST", "0.0.0.0"),
            port=_int_env("PRISM_DRIFT_MONITOR_PORT", 9109),
            incident_engine_url=os.getenv(
                "PRISM_INCIDENT_ENGINE_URL", "http://127.0.0.1:9108"
            ).strip(),
            baseline_samples=_int_env("PRISM_DRIFT_BASELINE_SAMPLES", 20),
            window_size=_int_env("PRISM_DRIFT_WINDOW_SIZE", 10),
            ks_alpha=_float_env("PRISM_DRIFT_KS_ALPHA", 0.05),
            centroid_z=_float_env("PRISM_DRIFT_CENTROID_Z", 2.5),
        )
