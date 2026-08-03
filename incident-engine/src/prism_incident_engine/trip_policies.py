"""FSM runtime knobs (window size + cooldown).

Trip *thresholds* live in ``policies/rego/*.rego`` (Phase 18). This YAML only
sizes the rolling ingestion buffer and the open→half_open cooldown so the FSM
and Rego window_min stay aligned — it is not the trip source of truth.
"""

from __future__ import annotations

from dataclasses import dataclass
from importlib import resources
from pathlib import Path

import yaml


@dataclass(frozen=True)
class TripPolicies:
    quarantine_rate_window: int
    cooldown_seconds: float


def load_policies(path: Path | None = None) -> TripPolicies:
    if path is None:
        ref = resources.files("prism_incident_engine.policies").joinpath("default_policies.yaml")
        raw = yaml.safe_load(ref.read_text(encoding="utf-8"))
    else:
        raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    policies = raw.get("policies") or {}
    qr = policies.get("quarantine_rate") or {}
    return TripPolicies(
        quarantine_rate_window=int(qr.get("window_batches", 5)),
        cooldown_seconds=float(raw.get("cooldown_seconds", 8.0)),
    )
