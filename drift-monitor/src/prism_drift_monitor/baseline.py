"""Baseline accumulation with an honest readiness gate (ADR-005 / Argus's
``baseline_ready`` discipline).

Only ``synthetic_scenario=False`` observations ever count toward the real
baseline -- scenario-engine's chaos events (including its deliberately
drift-shifted ``drift_signature`` outcome) are exactly the kind of synthetic
data Argus's ADR-007 separate-sink rule says must never co-own a real
reference. They are fully eligible for the *comparison window* (see
tracker.py) -- checking whether *current* traffic has drifted away from an
*earned* baseline is exactly the point -- they just can never help build
that baseline in the first place.

Until a real baseline exists, a "synthetic Gaussian" cold-start placeholder
is held (see ``ColdStartPlaceholder``) but it is structural only: nothing in
this module or ``tracker.py`` ever runs a statistical test against it. It
exists so ``/v1/status`` always has a non-null shape to show, labeled
unambiguously as a placeholder, and it is discarded (simply never
referenced again) the moment the real baseline freezes.
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class ColdStartPlaceholder:
    """Fabricated, standard-normal placeholder -- NEVER used for detection.
    Exists only so status endpoints have a non-null shape before a real
    baseline exists. See module docstring."""

    mode: str = "cold_start_synthetic_placeholder"
    note: str = (
        "Fabricated standard-normal values. Never used for detection "
        "(ADR-005) -- structural placeholder only, discarded once the "
        "real baseline freezes."
    )


def cold_start_placeholder() -> ColdStartPlaceholder:
    return ColdStartPlaceholder()


@dataclass(frozen=True)
class RealScalarBaseline:
    """Earned baseline for a scalar (per-feature) group, e.g.
    ``telemetry_numeric``. Frozen once enough real samples exist."""

    sample_count: int
    values: dict[str, list[float]] = field(default_factory=dict)

    def as_status(self) -> dict:
        return {"mode": "real", "sample_count": self.sample_count}


@dataclass(frozen=True)
class RealVectorBaseline:
    """Earned baseline for a vector group, e.g. ``cv_geometry``. Frozen once
    enough real samples exist."""

    sample_count: int
    vectors: list[list[float]] = field(default_factory=list)

    def as_status(self) -> dict:
        return {"mode": "real", "sample_count": self.sample_count}
