"""Orchestrates per-(asset_id, group) trackers, feature extraction, and
best-effort reporting of detected drift to incident-engine."""

from __future__ import annotations

from typing import Any

from prism_drift_monitor.config import DriftConfig
from prism_drift_monitor.features import cv_geometry_vector, telemetry_numeric_features
from prism_drift_monitor.incident_client import report_drift
from prism_drift_monitor.tracker import DriftResult, ScalarGroupTracker, VectorGroupTracker

TELEMETRY_GROUP = "telemetry_numeric"
CV_GROUP = "cv_geometry"


class DriftStore:
    def __init__(self, config: DriftConfig) -> None:
        self.config = config
        self._scalar_trackers: dict[str, ScalarGroupTracker] = {}
        self._vector_trackers: dict[str, VectorGroupTracker] = {}
        self.last_results: dict[str, DriftResult] = {}

    def _scalar_tracker(self, asset_id: str) -> ScalarGroupTracker:
        if asset_id not in self._scalar_trackers:
            self._scalar_trackers[asset_id] = ScalarGroupTracker(
                asset_id=asset_id,
                group=TELEMETRY_GROUP,
                baseline_samples=self.config.baseline_samples,
                window_size=self.config.window_size,
                ks_alpha=self.config.ks_alpha,
            )
        return self._scalar_trackers[asset_id]

    def _vector_tracker(self, asset_id: str) -> VectorGroupTracker:
        if asset_id not in self._vector_trackers:
            self._vector_trackers[asset_id] = VectorGroupTracker(
                asset_id=asset_id,
                group=CV_GROUP,
                baseline_samples=self.config.baseline_samples,
                window_size=self.config.window_size,
                ks_alpha=self.config.ks_alpha,
                centroid_z=self.config.centroid_z,
            )
        return self._vector_trackers[asset_id]

    def observe_telemetry(
        self, asset_id: str, payload: dict[str, Any], *, synthetic: bool
    ) -> DriftResult | None:
        features = telemetry_numeric_features(payload)
        if not features:
            return None
        result = self._scalar_tracker(asset_id).observe(features, synthetic=synthetic)
        return self._maybe_report(result)

    def observe_cv_finding(
        self, asset_id: str, finding: dict[str, Any], *, synthetic: bool
    ) -> DriftResult | None:
        vector = cv_geometry_vector(finding)
        result = self._vector_tracker(asset_id).observe(vector, synthetic=synthetic)
        return self._maybe_report(result)

    def _maybe_report(self, result: DriftResult | None) -> DriftResult | None:
        if result is None:
            return None
        self.last_results[f"{result.asset_id}:{result.group}"] = result
        report_drift(
            self.config.incident_engine_url,
            asset_id=result.asset_id,
            drifted_feature_count=result.drifted_feature_count,
            detail={
                "group": result.group,
                "tests": [
                    {
                        "feature": t.feature,
                        "test": t.test,
                        "drifted": t.drifted,
                        "statistic": t.statistic,
                        **t.detail,
                    }
                    for t in result.tests
                ],
            },
        )
        return result

    def status(self) -> dict[str, Any]:
        assets = sorted(set(self._scalar_trackers) | set(self._vector_trackers))
        out: dict[str, Any] = {}
        for asset_id in assets:
            groups: dict[str, Any] = {}
            if asset_id in self._scalar_trackers:
                groups[TELEMETRY_GROUP] = self._scalar_trackers[asset_id].status()
            if asset_id in self._vector_trackers:
                groups[CV_GROUP] = self._vector_trackers[asset_id].status()
            last = {
                group: {
                    "drifted_feature_count": r.drifted_feature_count,
                    "tests": [
                        {"feature": t.feature, "test": t.test, "drifted": t.drifted}
                        for t in r.tests
                    ],
                }
                for group in (TELEMETRY_GROUP, CV_GROUP)
                if (r := self.last_results.get(f"{asset_id}:{group}")) is not None
            }
            out[asset_id] = {"groups": groups, "last_detection": last}
        return out

    def baseline_ready(self) -> bool:
        """True only when every tracked (asset_id, group) has an earned
        baseline. False (honestly) if nothing has been tracked yet at all --
        there is no baseline to be ready."""
        trackers = [*self._scalar_trackers.values(), *self._vector_trackers.values()]
        if not trackers:
            return False
        return all(t.baseline_ready for t in trackers)
