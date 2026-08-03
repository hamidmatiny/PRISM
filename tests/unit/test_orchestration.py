"""Phase 17 — Dagster orchestration assets (ADR-006 / ADR-005 honesty)."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from dagster import build_asset_context, materialize
from fastapi.testclient import TestClient

from prism_orchestration.assets import (
    drift_status_snapshot,
    lakehouse_medallion,
    scenario_drift_reseed,
)
from prism_orchestration.clients import assets_with_drift
from prism_orchestration.definitions import all_assets, defs
from prism_scenario_engine.api import create_app as create_scenario_app
from prism_scenario_engine.config import ScenarioConfig


def _mat_meta(result: Any) -> dict[str, Any]:
    event = result.get_asset_materialization_events()[0]
    mat = event.materialization
    assert mat is not None
    return {k: v.value for k, v in mat.metadata.items()}


def test_definitions_load() -> None:
    keys = {a.key.to_user_string() for a in all_assets}
    assert keys == {
        "lakehouse_medallion",
        "drift_status_snapshot",
        "scenario_drift_reseed",
    }
    assert defs.resolve_job_def("prism_orchestration_job") is not None


def test_reseed_is_noop_when_flag_off(monkeypatch) -> None:
    monkeypatch.delenv("PRISM_DAGSTER_DRIFT_RESEED", raising=False)
    result = materialize([scenario_drift_reseed])
    assert result.success
    meta = _mat_meta(result)
    assert meta["status"] == "skipped"
    assert meta["reason"] == "flag_off"
    assert meta["reseed_attempted"] is False


def test_reseed_skips_when_flag_on_but_no_drift(monkeypatch, tmp_path: Path) -> None:
    import prism_orchestration.assets as assets_mod
    from prism_drift_monitor.api import create_app as create_drift_app
    from prism_drift_monitor.config import DriftConfig

    drift_app = create_drift_app(
        DriftConfig(
            baseline_samples=20,
            window_size=10,
            incident_engine_url="http://127.0.0.1:9",
        )
    )
    drift_client = TestClient(drift_app)

    def _status(url: str, *, timeout_s: float = 10.0) -> dict:
        return drift_client.get("/v1/status").json()

    monkeypatch.setattr(assets_mod, "get_drift_status", _status)
    monkeypatch.setenv("PRISM_DAGSTER_DRIFT_RESEED", "1")

    result = materialize([scenario_drift_reseed])
    assert result.success
    meta = _mat_meta(result)
    assert meta["status"] == "skipped"
    assert meta["reason"] == "no_drift_detected"
    assert meta["reseed_attempted"] is False


def test_reseed_runs_when_flag_on_and_drift_present(monkeypatch, tmp_path: Path) -> None:
    import prism_orchestration.assets as assets_mod
    import prism_orchestration.clients as clients

    monkeypatch.setenv("PRISM_DAGSTER_DRIFT_RESEED", "1")
    monkeypatch.setattr(
        clients,
        "get_drift_status",
        lambda url, timeout_s=10.0: {
            "baseline_ready": True,
            "assets": {
                "PRISM-AST-001": {
                    "groups": {},
                    "last_detection": {
                        "telemetry_numeric": {"drifted_feature_count": 3, "tests": []}
                    },
                }
            },
        },
    )

    scn = create_scenario_app(
        ScenarioConfig(
            data_root=tmp_path / "scn",
            seed=1,
            scenario_id="scn_boot",
            asset_ids=("PRISM-AST-001",),
        )
    )
    scn_client = TestClient(scn)

    def _reset(url, *, seed, scenario_id=None, weights=None, timeout_s=10.0):
        body = {"seed": seed, "scenario_id": scenario_id, "weights": weights}
        return scn_client.post("/v1/reset", json=body).json()

    def _pull(url, *, ticks, timeout_s=10.0):
        return [scn_client.get("/v1/next-event").json() for _ in range(ticks)]

    monkeypatch.setattr(clients, "reset_scenario", _reset)
    monkeypatch.setattr(clients, "pull_next_events", _pull)
    monkeypatch.setattr(assets_mod, "pull_next_events", _pull)
    monkeypatch.setattr(assets_mod, "reset_scenario", _reset)
    monkeypatch.setattr(assets_mod, "get_drift_status", clients.get_drift_status)

    result = materialize([scenario_drift_reseed])
    assert result.success
    meta = _mat_meta(result)
    assert meta["status"] == "ok"
    assert meta["reseed_attempted"] is True
    assert meta["ticks_pulled"] == 5
    assert all(o == "drift_signature" for o in meta["outcomes"])


def test_assets_with_drift_helper() -> None:
    status = {
        "assets": {
            "PRISM-AST-001": {
                "last_detection": {"telemetry_numeric": {"drifted_feature_count": 2}}
            },
            "PRISM-AST-002": {
                "last_detection": {"telemetry_numeric": {"drifted_feature_count": 0}}
            },
        }
    }
    found = assets_with_drift(status)
    assert len(found) == 1
    assert found[0]["asset_id"] == "PRISM-AST-001"


def test_lakehouse_asset_skips_without_java(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr("prism_orchestration.assets.shutil.which", lambda name: None)
    monkeypatch.setenv("PRISM_ORCH_BRONZE_ROOT", str(tmp_path))
    tmp_path.mkdir(exist_ok=True)
    ctx = build_asset_context()
    result = lakehouse_medallion(ctx)
    assert result.metadata["status"] == "skipped"
    assert result.metadata["reason"] == "java_not_on_path"


def test_drift_snapshot_skips_when_unreachable(monkeypatch) -> None:
    import prism_orchestration.assets as assets_mod

    def boom(url, timeout_s=10.0):
        raise ConnectionError("refused")

    monkeypatch.setattr(assets_mod, "get_drift_status", boom)
    ctx = build_asset_context()
    result = drift_status_snapshot(ctx)
    assert result.metadata["status"] == "skipped"
    assert result.metadata["reason"] == "drift_monitor_unreachable"


def test_scenario_reset_accepts_weights(tmp_path: Path) -> None:
    app = create_scenario_app(
        ScenarioConfig(
            data_root=tmp_path,
            seed=0,
            scenario_id="scn_0",
            asset_ids=("PRISM-AST-001",),
        )
    )
    client = TestClient(app)
    resp = client.post(
        "/v1/reset",
        json={
            "seed": 99,
            "scenario_id": "scn_w",
            "weights": {"drift_signature": 1.0},
        },
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["weights"]["drift_signature"] == 1.0
    ev = client.get("/v1/next-event").json()
    assert ev.get("skip") or ev.get("outcome") == "drift_signature"
