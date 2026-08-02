"""Outcome taxonomy and weight loading."""

from __future__ import annotations

from importlib import resources
from pathlib import Path
from typing import Literal

import yaml

Outcome = Literal[
    "clean",
    "sensor_corrupt",
    "contract_violation",
    "cv_low_confidence",
    "cv_high_confidence",
    "drift_signature",
    "stalled_source",
]

ALL_OUTCOMES: tuple[Outcome, ...] = (
    "clean",
    "sensor_corrupt",
    "contract_violation",
    "cv_low_confidence",
    "cv_high_confidence",
    "drift_signature",
    "stalled_source",
)


def load_weights(path: Path | None = None) -> dict[Outcome, float]:
    if path is None:
        ref = resources.files("prism_scenario_engine.weights").joinpath("default_weights.yaml")
        raw = yaml.safe_load(ref.read_text(encoding="utf-8"))
    else:
        raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    outcomes = raw.get("outcomes") or {}
    weights: dict[Outcome, float] = {}
    for name in ALL_OUTCOMES:
        weights[name] = float(outcomes.get(name, 0.0))
    total = sum(weights.values())
    if total <= 0:
        raise ValueError("outcome weights must sum to a positive value")
    return {k: v / total for k, v in weights.items()}
