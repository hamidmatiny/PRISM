"""Per-(asset_id, group) drift tracking: accumulate a real baseline, then
run the real statistical tests against a rolling comparison window.

Lifecycle for one tracker:
  1. Real (non-synthetic) observations accumulate into the baseline buffer.
  2. Once ``baseline_samples`` real observations exist, the baseline freezes
     (``RealScalarBaseline`` / ``RealVectorBaseline``) and ``baseline_ready``
     flips true -- permanently, for this tracker's lifetime; the buffer is
     never re-accumulated or re-frozen. This is the ADR-005 gate: nothing
     below this point runs before ``baseline_ready`` is true.
  3. Every observation from here on (synthetic or real -- see baseline.py's
     module docstring for why that's the correct, honest split) feeds a
     rolling comparison window. Once the window is full, every new sample
     re-runs the statistical test(s) fresh against the still-frozen
     baseline and the current window contents.
"""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass, field
from typing import Literal

from prism_drift_monitor.baseline import (
    ColdStartPlaceholder,
    RealScalarBaseline,
    RealVectorBaseline,
    cold_start_placeholder,
)
from prism_drift_monitor.detector import (
    FeatureTestResult,
    centroid_distance,
    ks_on_norms,
    ks_per_feature,
)

GroupKind = Literal["scalar", "vector"]


@dataclass
class DriftResult:
    asset_id: str
    group: str
    drifted_feature_count: int
    tests: list[FeatureTestResult]


@dataclass
class ScalarGroupTracker:
    asset_id: str
    group: str
    baseline_samples: int
    window_size: int
    ks_alpha: float
    _buffer: dict[str, list[float]] = field(default_factory=dict)
    _buffer_count: int = 0
    _baseline: RealScalarBaseline | None = None
    _window: dict[str, deque] = field(default_factory=dict)
    _cold_start: ColdStartPlaceholder = field(default_factory=cold_start_placeholder)

    @property
    def baseline_ready(self) -> bool:
        return self._baseline is not None

    def observe(self, features: dict[str, float], *, synthetic: bool) -> DriftResult | None:
        if not self.baseline_ready:
            if not synthetic:
                for name, value in features.items():
                    self._buffer.setdefault(name, []).append(value)
                self._buffer_count += 1
                if self._buffer_count >= self.baseline_samples:
                    self._baseline = RealScalarBaseline(
                        sample_count=self._buffer_count, values=dict(self._buffer)
                    )
                    self._window = {name: deque(maxlen=self.window_size) for name in self._buffer}
            return None

        for name, value in features.items():
            self._window.setdefault(name, deque(maxlen=self.window_size)).append(value)
        if any(len(w) < self.window_size for w in self._window.values()) or not self._window:
            return None

        assert self._baseline is not None
        window_snapshot = {name: list(values) for name, values in self._window.items()}
        tests = ks_per_feature(self._baseline.values, window_snapshot, alpha=self.ks_alpha)
        drifted = sum(1 for t in tests if t.drifted)
        return DriftResult(
            asset_id=self.asset_id, group=self.group, drifted_feature_count=drifted, tests=tests
        )

    def status(self) -> dict:
        if self._baseline is not None:
            return {"baseline_ready": True, "baseline": self._baseline.as_status()}
        return {
            "baseline_ready": False,
            "baseline": {"real_sample_count": self._buffer_count} | vars(self._cold_start),
        }


@dataclass
class VectorGroupTracker:
    asset_id: str
    group: str
    baseline_samples: int
    window_size: int
    ks_alpha: float
    centroid_z: float
    _buffer: list[list[float]] = field(default_factory=list)
    _baseline: RealVectorBaseline | None = None
    _window: deque = field(default_factory=lambda: deque())
    _cold_start: ColdStartPlaceholder = field(default_factory=cold_start_placeholder)

    def __post_init__(self) -> None:
        self._window = deque(maxlen=self.window_size)

    @property
    def baseline_ready(self) -> bool:
        return self._baseline is not None

    def observe(self, vector: list[float], *, synthetic: bool) -> DriftResult | None:
        if not self.baseline_ready:
            if not synthetic:
                self._buffer.append(vector)
                if len(self._buffer) >= self.baseline_samples:
                    self._baseline = RealVectorBaseline(
                        sample_count=len(self._buffer), vectors=list(self._buffer)
                    )
            return None

        self._window.append(vector)
        if len(self._window) < self.window_size:
            return None

        assert self._baseline is not None
        window_snapshot = list(self._window)
        centroid = centroid_distance(self._baseline.vectors, window_snapshot, z=self.centroid_z)
        norm = ks_on_norms(self._baseline.vectors, window_snapshot, alpha=self.ks_alpha)
        tests = [centroid, norm]
        drifted = sum(1 for t in tests if t.drifted)
        return DriftResult(
            asset_id=self.asset_id, group=self.group, drifted_feature_count=drifted, tests=tests
        )

    def status(self) -> dict:
        if self._baseline is not None:
            return {"baseline_ready": True, "baseline": self._baseline.as_status()}
        return {
            "baseline_ready": False,
            "baseline": {"real_sample_count": len(self._buffer)} | vars(self._cold_start),
        }
