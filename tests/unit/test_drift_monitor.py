"""drift-monitor — honest-baseline drift detection (Phase 16)."""

from __future__ import annotations

import random

import pytest
from fastapi.testclient import TestClient

from prism_drift_monitor.api import create_app
from prism_drift_monitor.config import DriftConfig
from prism_drift_monitor.detector import centroid_distance, ks_on_norms, ks_per_feature


@pytest.fixture
def client() -> TestClient:
    cfg = DriftConfig(baseline_samples=6, window_size=6, ks_alpha=0.05, centroid_z=2.0)
    return TestClient(create_app(cfg))


def _clean_ping(rng: random.Random, tick: int) -> dict:
    return {
        "speed_mph": 40.0 + rng.random(),
        "latitude": 37.0,
        "longitude": -122.0,
        "heading_deg": 90.0,
        "odometer_km": 1000.0 + tick,  # deliberately excluded from drift features
        "fuel_level_pct": 80.0,
    }


def _shifted_ping(rng: random.Random, tick: int) -> dict:
    return {
        "speed_mph": 95.0 + rng.random(),
        "latitude": 37.5,
        "longitude": -122.5,
        "heading_deg": 90.0,
        "odometer_km": 2000.0 + tick,
        "fuel_level_pct": 80.0,
    }


def test_health_reports_non_ready_before_any_observations(client: TestClient) -> None:
    body = client.get("/health").json()
    assert body["baseline_ready"] is False
    assert body["assets"] == {}


def test_baseline_never_built_from_synthetic_observations(client: TestClient) -> None:
    rng = random.Random(1)
    for i in range(20):
        r = client.post(
            "/v1/observe",
            json={
                "asset_id": "PRISM-AST-001",
                "group": "telemetry_numeric",
                "payload": _clean_ping(rng, i),
                "synthetic_scenario": True,  # must never count toward baseline
            },
        )
        assert r.status_code == 200
    status = client.get("/v1/status").json()
    telemetry_status = status["assets"]["PRISM-AST-001"]["groups"]["telemetry_numeric"]
    assert telemetry_status["baseline_ready"] is False
    assert status["baseline_ready"] is False


def test_baseline_freezes_after_configured_real_sample_count(client: TestClient) -> None:
    rng = random.Random(2)
    for i in range(5):
        client.post(
            "/v1/observe",
            json={
                "asset_id": "PRISM-AST-001",
                "group": "telemetry_numeric",
                "payload": _clean_ping(rng, i),
                "synthetic_scenario": False,
            },
        )
    not_ready = client.get("/v1/status").json()
    not_ready_group = not_ready["assets"]["PRISM-AST-001"]["groups"]["telemetry_numeric"]
    assert not_ready_group["baseline_ready"] is False

    client.post(
        "/v1/observe",
        json={
            "asset_id": "PRISM-AST-001",
            "group": "telemetry_numeric",
            "payload": _clean_ping(rng, 5),
            "synthetic_scenario": False,
        },
    )
    ready = client.get("/v1/status").json()
    group = ready["assets"]["PRISM-AST-001"]["groups"]["telemetry_numeric"]
    assert group["baseline_ready"] is True
    assert group["baseline"]["sample_count"] == 6


def test_stable_traffic_after_baseline_never_flags_drift(client: TestClient) -> None:
    rng = random.Random(3)
    for i in range(6):
        client.post(
            "/v1/observe",
            json={
                "asset_id": "PRISM-AST-001",
                "group": "telemetry_numeric",
                "payload": _clean_ping(rng, i),
                "synthetic_scenario": False,
            },
        )
    last = None
    for i in range(6, 12):
        last = client.post(
            "/v1/observe",
            json={
                "asset_id": "PRISM-AST-001",
                "group": "telemetry_numeric",
                "payload": _clean_ping(rng, i),
                "synthetic_scenario": False,
            },
        ).json()
    assert last["detection_ran"] is True
    assert last["drifted_feature_count"] == 0


def test_shifted_traffic_after_baseline_flags_drift_on_shifted_features_only(
    client: TestClient,
) -> None:
    rng = random.Random(4)
    for i in range(6):
        client.post(
            "/v1/observe",
            json={
                "asset_id": "PRISM-AST-001",
                "group": "telemetry_numeric",
                "payload": _clean_ping(rng, i),
                "synthetic_scenario": False,
            },
        )
    last = None
    # scenario-engine's real drift_signature carries synthetic_scenario=True --
    # confirming detection still runs on synthetic *window* traffic (only the
    # baseline itself is synthetic-blind, see test above).
    for i in range(6, 12):
        last = client.post(
            "/v1/observe",
            json={
                "asset_id": "PRISM-AST-001",
                "group": "telemetry_numeric",
                "payload": _shifted_ping(rng, i),
                "synthetic_scenario": True,
            },
        ).json()
    assert last["detection_ran"] is True
    drifted = {t["feature"] for t in last["tests"] if t["drifted"]}
    assert drifted == {"speed_mph", "latitude", "longitude"}
    assert last["drifted_feature_count"] >= 2  # >= incident-engine's default policy threshold


def test_cv_geometry_vector_group_detects_shifted_findings(client: TestClient) -> None:
    rng = random.Random(5)

    def finding(conf: float, w: float, h: float, cls: str) -> dict:
        return {
            "confidence": conf,
            "bounding_box": {"x": 0, "y": 0, "width": w, "height": h},
            "defect_class": cls,
        }

    for _i in range(6):
        client.post(
            "/v1/observe",
            json={
                "asset_id": "PRISM-AST-002",
                "group": "cv_geometry",
                "payload": finding(0.6 + rng.random() * 0.05, 40 + rng.random() * 5, 30, "dent"),
                "synthetic_scenario": False,
            },
        )
    last = None
    for _ in range(6):
        last = client.post(
            "/v1/observe",
            json={
                "asset_id": "PRISM-AST-002",
                "group": "cv_geometry",
                "payload": finding(0.97, 300, 300, "anomaly"),
                "synthetic_scenario": False,
            },
        ).json()
    assert last["detection_ran"] is True
    tests_by_name = {t["test"]: t["drifted"] for t in last["tests"]}
    assert tests_by_name["centroid_distance"] is True
    assert tests_by_name["ks_norm"] is True


def test_ks_per_feature_pure_function() -> None:
    baseline = {"speed": [40.0, 41.0, 39.5, 40.2, 40.8, 39.9]}
    window = {"speed": [90.0, 91.0, 89.5, 90.2, 90.8, 89.9]}
    results = ks_per_feature(baseline, window, alpha=0.05)
    assert len(results) == 1
    assert results[0].drifted is True


def test_centroid_distance_pure_function() -> None:
    baseline = [[0.0, 0.0], [0.1, 0.0], [0.0, 0.1], [0.1, 0.1]]
    window = [[10.0, 10.0], [10.1, 10.0], [10.0, 10.1], [10.1, 10.1]]
    result = centroid_distance(baseline, window, z=2.0)
    assert result.drifted is True


def test_ks_on_norms_pure_function() -> None:
    baseline = [[1.0, 0.0], [1.1, 0.0], [0.9, 0.0], [1.0, 0.1]]
    window = [[5.0, 0.0], [5.1, 0.0], [4.9, 0.0], [5.0, 0.1]]
    result = ks_on_norms(baseline, window, alpha=0.05)
    assert result.drifted is True
