"""Trip-policy loading — declarative YAML today, real OPA/Rego in Phase 18."""

from __future__ import annotations

from dataclasses import dataclass
from importlib import resources
from pathlib import Path

import yaml


@dataclass(frozen=True)
class TripPolicies:
    quarantine_rate_window: int
    quarantine_rate_threshold: float
    consecutive_qa_failures_threshold: int
    drifted_features_threshold: int
    cooldown_seconds: float


def load_policies(path: Path | None = None) -> TripPolicies:
    if path is None:
        ref = resources.files("prism_incident_engine.policies").joinpath("default_policies.yaml")
        raw = yaml.safe_load(ref.read_text(encoding="utf-8"))
    else:
        raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    policies = raw.get("policies") or {}
    qr = policies.get("quarantine_rate") or {}
    cqf = policies.get("consecutive_qa_failures") or {}
    df = policies.get("drifted_features") or {}
    return TripPolicies(
        quarantine_rate_window=int(qr.get("window_batches", 5)),
        quarantine_rate_threshold=float(qr.get("threshold", 0.15)),
        consecutive_qa_failures_threshold=int(cqf.get("threshold", 3)),
        drifted_features_threshold=int(df.get("threshold", 2)),
        cooldown_seconds=float(raw.get("cooldown_seconds", 8.0)),
    )
