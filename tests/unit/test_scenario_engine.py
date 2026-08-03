"""Phase 12 — scenario-engine seed replay + synthetic labeling."""

from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient
from prism_scenario_engine.api import create_app
from prism_scenario_engine.config import ScenarioConfig
from prism_scenario_engine.journal import ScenarioJournal
from prism_scenario_engine.outcomes import load_weights
from prism_scenario_engine.sampler import ScenarioSampler

from prism_ingestion.config import IngestConfig
from prism_ingestion.pipeline import IngestPipeline
from prism_ingestion.sources import ScenarioClient
from prism_ingestion.validate import validate_event
from prism_telemetry_schema import CameraFrameMetadata, SensorPing


def _run_journal(root: Path, seed: int = 42, ticks: int = 40) -> Path:
    cfg = ScenarioConfig(
        data_root=root,
        seed=seed,
        scenario_id=f"scn_{seed}",
        asset_ids=("PRISM-AST-001", "PRISM-AST-002", "PRISM-AST-003"),
    )
    client = TestClient(create_app(cfg))
    for _ in range(ticks):
        client.get("/v1/next-event")
    return cfg.journal_dir / f"scn_{seed}.jsonl"


def test_seed_replay_journals_are_byte_identical(tmp_path: Path) -> None:
    a = _run_journal(tmp_path / "a")
    b = _run_journal(tmp_path / "b")
    assert a.read_text(encoding="utf-8") == b.read_text(encoding="utf-8")
    assert a.stat().st_size > 100


def test_synthetic_flags_on_emitted_events(tmp_path: Path) -> None:
    journal = ScenarioJournal(tmp_path / "journal", "scn_7")
    sampler = ScenarioSampler(
        seed=7,
        scenario_id="scn_7",
        asset_ids=("PRISM-AST-001",),
        journal=journal,
        weights=load_weights(),
    )
    seen_emit = False
    for _ in range(30):
        envelope = sampler.next_event()
        if envelope.get("skip"):
            continue
        seen_emit = True
        payload = envelope["payload"]
        assert payload["synthetic_scenario"] is True
        assert payload["scenario_id"] == "scn_7"
        kind = envelope["kind"]
        ok, cleaned, err = validate_event(kind, payload)
        if ok:
            if kind == "sensor_ping":
                SensorPing.model_validate(cleaned)
            else:
                CameraFrameMetadata.model_validate(cleaned)
            assert cleaned["synthetic_scenario"] is True
        else:
            # Corrupt outcomes must still carry synthetic labels in the raw payload.
            assert payload.get("synthetic_scenario") is True
    assert seen_emit


def test_weights_sum_to_one() -> None:
    weights = load_weights()
    assert abs(sum(weights.values()) - 1.0) < 1e-9
    assert set(weights) >= {"clean", "stalled_source", "sensor_corrupt"}


def test_ingestion_scenario_source_mode(tmp_path: Path) -> None:
    cfg = ScenarioConfig(
        data_root=tmp_path / "scn",
        seed=99,
        scenario_id="scn_99",
        asset_ids=("PRISM-AST-001", "PRISM-AST-002"),
    )
    server = TestClient(create_app(cfg))

    class _LocalScenario(ScenarioClient):
        def generate_event(self):  # type: ignore[no-untyped-def]
            body = server.get("/v1/next-event").json()
            if body.get("skip"):
                return None
            return body["kind"], body["payload"]

    ingest_cfg = IngestConfig(
        backend="file",
        source_mode="scenario",
        scenario_url="http://scenario-engine:9107",
        data_root=tmp_path / "ingest",
        emit_rate_hz=10.0,
        failure_rate=0.0,
        duration_seconds=0.0,
        seed=99,
    )
    pipeline = IngestPipeline.from_config(ingest_cfg)
    pipeline.source = _LocalScenario("http://unused")
    accepted = rejected = skipped = 0
    for _ in range(25):
        before_a, before_r, before_s = (
            pipeline.stats.accepted,
            pipeline.stats.rejected,
            pipeline.stats.skipped,
        )
        pipeline.process_one()
        if pipeline.stats.accepted > before_a:
            accepted += 1
        elif pipeline.stats.rejected > before_r:
            rejected += 1
        elif pipeline.stats.skipped > before_s:
            skipped += 1
    assert accepted + rejected + skipped == 25
    assert accepted >= 1
    # At least one accepted bronze record is labeled synthetic.
    bronze_files = list((tmp_path / "ingest" / "bronze").rglob("*.json"))
    assert bronze_files
    import json

    sample = json.loads(bronze_files[0].read_text(encoding="utf-8"))
    assert sample.get("synthetic_scenario") is True
    assert sample.get("scenario_id") == "scn_99"


def test_reset_starts_fresh_seeded_run_without_disturbing_prior_journal(tmp_path: Path) -> None:
    """Phase 15 cockpit scenario controls: POST /v1/reset must (a) actually change
    the RNG sequence going forward, and (b) never touch the journal file from
    whatever run was active before the reset -- otherwise replaying an earlier
    seed later would no longer be byte-identical, breaking Phase 12's guarantee."""
    cfg = ScenarioConfig(
        data_root=tmp_path,
        seed=1,
        scenario_id="scn_1",
        asset_ids=("PRISM-AST-001",),
    )
    client = TestClient(create_app(cfg))

    # Drive a few ticks under the original seed=1 run and capture its journal content.
    for _ in range(5):
        client.get("/v1/next-event")
    original_journal_path = cfg.journal_dir / "scn_1.jsonl"
    original_content = original_journal_path.read_text(encoding="utf-8")
    assert original_content

    # Reset to a different seed.
    resp = client.post("/v1/reset", json={"seed": 999})
    assert resp.status_code == 200
    body = resp.json()
    assert body["seed"] == 999
    assert body["tick"] == 0
    assert body["scenario_id"].startswith("scn_999_")

    # /health and /v1/status now report the NEW seed/scenario_id, not the old one.
    health = client.get("/health").json()
    assert health["seed"] == 999
    assert health["scenario_id"] == body["scenario_id"]
    assert health["tick"] == 0

    # The original run's journal file is untouched by the reset.
    assert original_journal_path.read_text(encoding="utf-8") == original_content

    # New ticks now land in the NEW journal file, not the old one.
    for _ in range(3):
        client.get("/v1/next-event")
    new_journal_path = cfg.journal_dir / f"{body['scenario_id']}.jsonl"
    assert new_journal_path.exists()
    assert original_journal_path.read_text(encoding="utf-8") == original_content
    status = client.get("/v1/status").json()
    assert status["seed"] == 999
    assert status["tick"] == 3


def test_reset_with_explicit_scenario_id_is_honored(tmp_path: Path) -> None:
    cfg = ScenarioConfig(data_root=tmp_path, seed=1, scenario_id="scn_1")
    client = TestClient(create_app(cfg))
    resp = client.post("/v1/reset", json={"seed": 42, "scenario_id": "my-custom-run"})
    assert resp.status_code == 200
    assert resp.json()["scenario_id"] == "my-custom-run"
    assert (cfg.journal_dir / "my-custom-run.jsonl").exists()
