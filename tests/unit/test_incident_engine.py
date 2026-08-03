"""incident-engine — per-asset circuit breaker FSM and API (Phase 14/18)."""

from __future__ import annotations

import shutil
import time
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from prism_incident_engine.api import create_app
from prism_incident_engine.config import IncidentConfig
from prism_incident_engine.opa_client import UnavailablePolicyEngine
from prism_incident_engine.trip_policies import TripPolicies

REPO = Path(__file__).resolve().parents[2]
REGO_DIR = REPO / "incident-engine" / "policies" / "rego"
OPA_BIN = shutil.which("opa") or str(REPO / ".venv" / "bin" / "opa")


@pytest.fixture
def client(tmp_path: Path) -> TestClient:
    if not Path(OPA_BIN).is_file():
        pytest.skip("opa binary required for incident-engine trip tests")
    cfg = IncidentConfig(
        data_root=tmp_path / "data",
        port=19108,
        opa_url=None,
        opa_policy_dir=REGO_DIR,
        opa_bin=OPA_BIN,
    )
    app = create_app(cfg)
    # Keep Rego trip thresholds; only shrink cooldown for fast probe tests.
    app.state.store.policies = TripPolicies(
        quarantine_rate_window=5,
        cooldown_seconds=0.3,
    )
    # Re-bind breakers created later to the updated window size via new policies.
    app.state.store._breakers.clear()
    return TestClient(app)


def _observe(client: TestClient, asset_id: str, kind: str, detail: dict | None = None) -> dict:
    body: dict = {"asset_id": asset_id, "kind": kind}
    if detail:
        body["detail"] = detail
    r = client.post("/v1/observations", json=body)
    assert r.status_code == 200, r.text
    return r.json()


def test_health_reports_rego_policy_engine(client: TestClient) -> None:
    h = client.get("/health").json()
    assert h["policy_engine"]["ready"] is True
    assert h["policy_engine"]["source_of_truth"] == "rego"
    assert h["policy_engine"]["mode"] == "eval"
    assert "quarantine_rate" not in h.get("policies", {})


def test_quarantine_rate_trips_one_asset_others_stay_closed(client: TestClient) -> None:
    for _ in range(5):
        state = _observe(client, "PRISM-AST-001", "ingestion_quarantined")
    assert state["state"] == "open"
    assert state["trip_reason"] == "quarantine_rate"

    for _ in range(5):
        other = _observe(client, "PRISM-AST-002", "ingestion_accepted")
    assert other["state"] == "closed"

    snapshot = client.get("/breakers").json()
    states = {b["asset_id"]: b["state"] for b in snapshot["breakers"]}
    assert states == {"PRISM-AST-001": "open", "PRISM-AST-002": "closed"}


def test_consecutive_qa_failures_trips_breaker(client: TestClient) -> None:
    for _ in range(2):
        state = _observe(client, "PRISM-AST-003", "qa_fail")
    assert state["state"] == "closed"
    state = _observe(client, "PRISM-AST-003", "qa_fail")
    assert state["state"] == "open"
    assert state["trip_reason"] == "consecutive_qa_failures"

    state2 = _observe(client, "PRISM-AST-003", "qa_pass")
    assert state2["consecutive_qa_failures"] in (0, 1)


def test_retrip_while_open_refreshes_same_incident(client: TestClient) -> None:
    for _ in range(5):
        _observe(client, "PRISM-AST-004", "ingestion_quarantined")
    incident_id = client.get("/incidents?status=open").json()["incidents"][0]["incident_id"]

    _observe(client, "PRISM-AST-004", "ingestion_quarantined")
    incident = client.get(f"/incidents/{incident_id}").json()
    assert incident["incident_id"] == incident_id
    assert incident["trip_count"] == 2


def test_cooldown_then_good_probe_auto_resolves(client: TestClient) -> None:
    for _ in range(5):
        _observe(client, "PRISM-AST-005", "ingestion_quarantined")
    incident_id = client.get("/incidents?status=open").json()["incidents"][0]["incident_id"]

    time.sleep(0.4)
    state = _observe(client, "PRISM-AST-005", "ingestion_accepted")
    assert state["state"] == "closed"
    assert state["incident_id"] is None

    incident = client.get(f"/incidents/{incident_id}").json()
    assert incident["status"] == "resolved"


def test_cooldown_then_bad_probe_retrips(client: TestClient) -> None:
    for _ in range(5):
        _observe(client, "PRISM-AST-006", "ingestion_quarantined")
    incident_id = client.get("/incidents?status=open").json()["incidents"][0]["incident_id"]

    time.sleep(0.4)
    state = _observe(client, "PRISM-AST-006", "ingestion_quarantined")
    assert state["state"] == "open"

    incident = client.get(f"/incidents/{incident_id}").json()
    assert incident["incident_id"] == incident_id
    assert incident["status"] == "open"


def test_manual_acknowledge_and_resolve(client: TestClient) -> None:
    for _ in range(5):
        _observe(client, "PRISM-AST-007", "ingestion_quarantined")
    incident_id = client.get("/incidents?status=open").json()["incidents"][0]["incident_id"]

    ack = client.post(f"/incidents/{incident_id}/acknowledge")
    assert ack.status_code == 200
    assert ack.json()["status"] == "acknowledged"

    resolved = client.post(f"/incidents/{incident_id}/resolve")
    assert resolved.status_code == 200
    assert resolved.json()["status"] == "resolved"

    breaker = client.get("/breakers/PRISM-AST-007").json()
    assert breaker["state"] == "closed"
    assert breaker["incident_id"] is None


def test_unknown_incident_404(client: TestClient) -> None:
    assert client.get("/incidents/inc_doesnotexist").status_code == 404
    assert client.post("/incidents/inc_doesnotexist/acknowledge").status_code == 404
    assert client.post("/incidents/inc_doesnotexist/resolve").status_code == 404


def test_unknown_observation_kind_rejected(client: TestClient) -> None:
    r = client.post(
        "/v1/observations", json={"asset_id": "PRISM-AST-001", "kind": "not_a_real_kind"}
    )
    assert r.status_code == 400


def test_webhook_inbox_receives_incident_opened_with_escalation(client: TestClient) -> None:
    for _ in range(5):
        _observe(client, "PRISM-AST-008", "ingestion_quarantined")
    inbox = client.get("/v1/webhook-test/inbox").json()
    assert inbox["count"] >= 1
    opened = next(
        item
        for item in inbox["items"]
        if item.get("event") == "incident_opened" and item.get("asset_id") == "PRISM-AST-008"
    )
    assert opened["escalation"]["policy"] == "quarantine_rate"
    assert opened["escalation"]["severity"] == "medium"


def test_journal_records_transitions(client: TestClient) -> None:
    for _ in range(5):
        _observe(client, "PRISM-AST-009", "ingestion_quarantined")
    journal = client.get("/v1/journal").json()
    events = {e["event"] for e in journal["entries"]}
    assert "incident_opened" in events
    assert "breaker_transition" in events


def test_drifted_features_trips_via_rego(client: TestClient) -> None:
    state = _observe(client, "PRISM-AST-010", "drift", detail={"drifted_feature_count": 1})
    assert state["state"] == "closed"
    state = _observe(client, "PRISM-AST-010", "drift", detail={"drifted_feature_count": 2})
    assert state["state"] == "open"
    assert state["trip_reason"] == "drifted_features"


def test_opa_unreachable_fails_open_no_silent_yaml_fallback(tmp_path: Path) -> None:
    """ADR-005: unreachable OPA must not invent trips via old YAML thresholds."""
    cfg = IncidentConfig(
        data_root=tmp_path / "data",
        port=19109,
        opa_url="http://127.0.0.1:9",  # nothing listens
        opa_policy_dir=REGO_DIR,
    )
    app = create_app(cfg)
    # Force HTTP mode that cannot connect (override any eval fallback).
    app.state.store.policy_engine = UnavailablePolicyEngine()
    for b in app.state.store._breakers.values():
        b.policy_engine = app.state.store.policy_engine
    client = TestClient(app)

    health = client.get("/health").json()
    assert health["policy_engine"]["ready"] is False

    for _ in range(5):
        state = _observe(client, "PRISM-AST-099", "ingestion_quarantined")
    assert state["state"] == "closed"
    assert state["trip_reason"] is None
    assert state["policy_engine_error"] == "policy_engine_unavailable"
