"""Phase 16 — real scenario-engine + real ingestion + real drift-monitor +
real incident-engine, end to end: an earned baseline, then scenario-engine's
own foreshadowed ``drift_signature`` outcome actually trips an asset's
breaker via ``drifted_features`` -- not a mocked FSM, real HTTP throughout.
"""

from __future__ import annotations

import socket
import threading
from pathlib import Path

import httpx
import pytest
import uvicorn
import yaml

from prism_drift_monitor.api import create_app as create_drift_app
from prism_drift_monitor.config import DriftConfig
from prism_incident_engine.api import create_app as create_incident_app
from prism_incident_engine.config import IncidentConfig
from prism_incident_engine.trip_policies import TripPolicies
from prism_ingestion.config import IngestConfig
from prism_ingestion.pipeline import IngestPipeline
from prism_scenario_engine.api import create_app as create_scenario_app
from prism_scenario_engine.config import ScenarioConfig


def _free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return int(s.getsockname()[1])


def _wait_healthy(url: str) -> None:
    with httpx.Client() as client:
        for _ in range(150):
            try:
                if client.get(f"{url}/health", timeout=0.2).status_code == 200:
                    return
            except Exception:  # noqa: BLE001
                pass
    raise RuntimeError(f"service never became healthy: {url}")


def _run_uvicorn(app, port: int) -> None:
    threading.Thread(
        target=uvicorn.Server(
            uvicorn.Config(app, host="127.0.0.1", port=port, log_level="warning")
        ).run,
        daemon=True,
    ).start()


@pytest.fixture()
def three_live_services(tmp_path: Path):
    """Real incident-engine + real drift-monitor, both actual HTTP servers.
    incident-engine's other trip policies are pushed out of reach so only
    ``drifted_features`` can trip the breaker in this test."""
    incident_port = _free_port()
    drift_port = _free_port()

    incident_cfg = IncidentConfig(port=incident_port, data_root=tmp_path / "incident-data")
    incident_app = create_incident_app(incident_cfg)
    incident_app.state.store.policies = TripPolicies(
        quarantine_rate_window=3,
        quarantine_rate_threshold=1.1,  # unreachable — isolates this test to drift
        consecutive_qa_failures_threshold=999,  # unreachable
        drifted_features_threshold=2,
        cooldown_seconds=0.3,
    )
    _run_uvicorn(incident_app, incident_port)

    incident_url = f"http://127.0.0.1:{incident_port}"
    drift_cfg = DriftConfig(
        port=drift_port,
        incident_engine_url=incident_url,
        baseline_samples=15,
        window_size=8,
    )
    _run_uvicorn(create_drift_app(drift_cfg), drift_port)

    drift_url = f"http://127.0.0.1:{drift_port}"
    _wait_healthy(incident_url)
    _wait_healthy(drift_url)
    return incident_url, drift_url


def test_earned_baseline_then_real_drift_signature_trips_breaker(
    tmp_path: Path, three_live_services: tuple[str, str]
) -> None:
    incident_url, drift_url = three_live_services

    # -- Phase A: earn a real baseline from the live (non-synthetic) simulator --
    before = httpx.get(f"{drift_url}/health", timeout=2.0).json()
    assert before["baseline_ready"] is False

    live_config = IngestConfig(
        backend="file",
        source_mode="live",
        asset_ids=("PRISM-AST-001",),
        seed=42,
        failure_rate=0.0,
        incident_engine_url=incident_url,
        drift_monitor_url=drift_url,
        data_root=tmp_path / "live-data",
    )
    live_pipeline = IngestPipeline.from_config(live_config)
    sensor_pings = 0
    ticks = 0
    while sensor_pings < 20 and ticks < 200:
        accepted = live_pipeline.process_one()
        ticks += 1
        if accepted and live_pipeline.stats.sensor_pings > sensor_pings:
            sensor_pings = live_pipeline.stats.sensor_pings

    after = httpx.get(f"{drift_url}/health", timeout=2.0).json()
    assert after["baseline_ready"] is True, after
    status = httpx.get(f"{drift_url}/v1/status", timeout=2.0).json()
    telemetry_status = status["assets"]["PRISM-AST-001"]["groups"]["telemetry_numeric"]
    assert telemetry_status["baseline_ready"] is True

    # Nothing tripped yet -- clean live traffic, no drift.
    still_closed = httpx.get(f"{incident_url}/breakers/PRISM-AST-001", timeout=2.0).json()
    assert still_closed["state"] == "closed"

    # -- Phase B: scenario-engine, weighted 100% to its own foreshadowed
    # drift_signature outcome, feeds a real shifted window --
    weights_path = tmp_path / "all_drift.yaml"
    weights_path.write_text(
        yaml.safe_dump(
            {
                "outcomes": {
                    "clean": 0.0,
                    "sensor_corrupt": 0.0,
                    "contract_violation": 0.0,
                    "cv_low_confidence": 0.0,
                    "cv_high_confidence": 0.0,
                    "drift_signature": 1.0,
                    "stalled_source": 0.0,
                }
            }
        ),
        encoding="utf-8",
    )
    scenario_port = _free_port()
    scenario_cfg = ScenarioConfig(
        data_root=tmp_path / "scenario-data",
        seed=7,
        scenario_id="scn_drift_test",
        asset_ids=("PRISM-AST-001",),
        weights_path=weights_path,
        port=scenario_port,
    )
    _run_uvicorn(create_scenario_app(scenario_cfg), scenario_port)
    scenario_url = f"http://127.0.0.1:{scenario_port}"
    _wait_healthy(scenario_url)

    scenario_config = IngestConfig(
        backend="file",
        source_mode="scenario",
        scenario_url=scenario_url,
        asset_ids=("PRISM-AST-001",),
        incident_engine_url=incident_url,
        drift_monitor_url=drift_url,
        data_root=tmp_path / "scenario-ingest-data",
    )
    scenario_pipeline = IngestPipeline.from_config(scenario_config)
    for _ in range(12):
        scenario_pipeline.process_one()

    # -- Phase C: the actual proof --
    breaker = httpx.get(f"{incident_url}/breakers/PRISM-AST-001", timeout=2.0).json()
    assert breaker["state"] == "open", breaker
    assert breaker["trip_reason"] == "drifted_features", breaker
    assert breaker["drifted_feature_count"] >= 2, breaker
