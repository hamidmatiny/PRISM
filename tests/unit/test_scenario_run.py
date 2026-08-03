"""Phase 15 — admin-triggered bounded scenario batch (cockpit "run scenario")."""

from __future__ import annotations

import socket
import threading
from pathlib import Path

import httpx
import pytest
import uvicorn

from prism_incident_engine.api import create_app as create_incident_app
from prism_incident_engine.config import IncidentConfig
from prism_ingestion.config import IngestConfig
from prism_ingestion.scenario_run import MAX_TICKS, ScenarioRunError, run_scenario_batch
from prism_scenario_engine.api import create_app as create_scenario_app
from prism_scenario_engine.config import ScenarioConfig


def _free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return int(s.getsockname()[1])


def _wait_healthy(url: str) -> None:
    with httpx.Client() as client:
        for _ in range(100):
            try:
                if client.get(f"{url}/health", timeout=0.2).status_code == 200:
                    return
            except Exception:  # noqa: BLE001
                pass
    raise RuntimeError(f"service never became healthy: {url}")


@pytest.fixture()
def live_services(tmp_path: Path):
    """Real scenario-engine + real incident-engine, both actual HTTP servers."""
    scenario_port = _free_port()
    incident_port = _free_port()

    scenario_cfg = ScenarioConfig(
        data_root=tmp_path / "scenario-data",
        seed=1,
        scenario_id="scn_1",
        asset_ids=("PRISM-AST-001", "PRISM-AST-002"),
        port=scenario_port,
    )
    incident_cfg = IncidentConfig(port=incident_port, data_root=tmp_path / "incident-data")

    threading.Thread(
        target=uvicorn.Server(
            uvicorn.Config(
                create_scenario_app(scenario_cfg),
                host="127.0.0.1",
                port=scenario_port,
                log_level="warning",
            )
        ).run,
        daemon=True,
    ).start()
    threading.Thread(
        target=uvicorn.Server(
            uvicorn.Config(
                create_incident_app(incident_cfg),
                host="127.0.0.1",
                port=incident_port,
                log_level="warning",
            )
        ).run,
        daemon=True,
    ).start()

    scenario_url = f"http://127.0.0.1:{scenario_port}"
    incident_url = f"http://127.0.0.1:{incident_port}"
    _wait_healthy(scenario_url)
    _wait_healthy(incident_url)
    return scenario_url, incident_url


def test_run_scenario_batch_drives_real_ticks_through_real_ingestion(
    tmp_path: Path, live_services: tuple[str, str]
) -> None:
    scenario_url, incident_url = live_services
    config = IngestConfig(
        backend="file",
        scenario_url=scenario_url,
        incident_engine_url=incident_url,
        data_root=tmp_path / "ingest-data",
    )

    result = run_scenario_batch(config, seed=42, ticks=20, rate_hz=20.0)

    assert result["seed"] == 42
    assert result["scenario_id"].startswith("scn_42_")
    assert result["ticks_requested"] == 20
    # emitted + skipped == ticks (each tick is either an emit or a stalled-source skip)
    assert result["emitted"] + result["skipped"] == 20
    assert result["accepted"] + result["rejected"] == result["emitted"]

    # Real bronze/DLQ files landed under this batch's own isolated data root.
    bronze_root = config.data_root / "bronze"
    assert bronze_root.exists()

    # Real observations reached the real incident-engine (best-effort reporting,
    # but with a live incident-engine up, "best effort" should mean "actually happened").
    breakers = httpx.get(f"{incident_url}/breakers", timeout=2.0).json()
    if result["accepted"] + result["rejected"] > 0:
        assert breakers["count"] >= 1


def test_run_scenario_batch_rejects_out_of_range_ticks(tmp_path: Path, live_services) -> None:
    scenario_url, incident_url = live_services
    config = IngestConfig(
        backend="file",
        scenario_url=scenario_url,
        incident_engine_url=incident_url,
        data_root=tmp_path / "ingest-data",
    )
    with pytest.raises(ScenarioRunError):
        run_scenario_batch(config, seed=1, ticks=0)
    with pytest.raises(ScenarioRunError):
        run_scenario_batch(config, seed=1, ticks=MAX_TICKS + 1)


def test_run_scenario_batch_rejects_out_of_range_rate(tmp_path: Path, live_services) -> None:
    scenario_url, incident_url = live_services
    config = IngestConfig(
        backend="file",
        scenario_url=scenario_url,
        incident_engine_url=incident_url,
        data_root=tmp_path / "ingest-data",
    )
    with pytest.raises(ScenarioRunError):
        run_scenario_batch(config, seed=1, ticks=5, rate_hz=0.01)
    with pytest.raises(ScenarioRunError):
        run_scenario_batch(config, seed=1, ticks=5, rate_hz=1000.0)


def test_run_scenario_batch_surfaces_reset_failure(tmp_path: Path) -> None:
    config = IngestConfig(
        backend="file",
        scenario_url="http://127.0.0.1:1",  # nothing listening -- guaranteed connection failure
        incident_engine_url="http://127.0.0.1:1",
        data_root=tmp_path / "ingest-data",
    )
    with pytest.raises(ScenarioRunError, match="scenario-engine reset failed"):
        run_scenario_batch(config, seed=1, ticks=5)


def test_run_scenario_batch_isolated_stats_do_not_touch_main_pipeline(
    tmp_path: Path, live_services: tuple[str, str]
) -> None:
    """The admin batch must not mutate any pre-existing, continuously-running
    pipeline's own stats -- it builds its own isolated IngestPipeline."""
    scenario_url, incident_url = live_services
    from prism_ingestion.pipeline import IngestPipeline

    main_config = IngestConfig(
        backend="file",
        source_mode="live",
        scenario_url=scenario_url,
        incident_engine_url=incident_url,
        data_root=tmp_path / "ingest-data",
    )
    main_pipeline = IngestPipeline.from_config(main_config)
    for _ in range(5):
        main_pipeline.process_one()
    before = main_pipeline.stats.as_dict()

    run_scenario_batch(main_config, seed=7, ticks=10, rate_hz=20.0)

    after = main_pipeline.stats.as_dict()
    assert before == after


def test_corrupted_asset_id_never_creates_a_phantom_breaker(
    tmp_path: Path, live_services: tuple[str, str]
) -> None:
    """Real bug found via the cockpit Breaker Board (not caught by any earlier
    test): on rejection, ``report_observation`` used to forward whatever raw,
    unvalidated ``asset_id`` string was in the corrupted payload -- including
    scenario-engine's own ``bad_id_pattern`` corruption strategy, which turns
    a real id into e.g. ``BAD-PRISM-AST-002``. incident-engine has no concept
    of "not a real asset" and happily created a permanent breaker entry for
    it, one that can never heal since nothing legitimate will ever report
    under that id. Forces failure_rate=1.0 so every event is corrupted --
    over enough ticks the uniformly-random corruption strategy pool is all
    but guaranteed to hit ``bad_id_pattern`` at least once."""
    scenario_url, incident_url = live_services
    from prism_ingestion.pipeline import IngestPipeline

    config = IngestConfig(
        backend="file",
        source_mode="live",
        failure_rate=1.0,
        seed=3,
        incident_engine_url=incident_url,
        data_root=tmp_path / "ingest-data",
    )
    pipeline = IngestPipeline.from_config(config)
    for _ in range(60):
        pipeline.process_one()

    stats = pipeline.stats.as_dict()
    assert stats["by_corruption_type"].get("malformed_identifier", 0) > 0, (
        "test didn't actually exercise the bad_id_pattern corruption -- "
        f"got corruption types: {stats['by_corruption_type']}"
    )

    breakers = httpx.get(f"{incident_url}/breakers", timeout=2.0).json()
    bad_ids = [b["asset_id"] for b in breakers["breakers"] if b["asset_id"].startswith("BAD-")]
    assert bad_ids == [], f"phantom breaker(s) created for corrupted asset_id: {bad_ids}"
