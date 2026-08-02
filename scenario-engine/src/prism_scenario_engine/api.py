"""FastAPI surface for scenario-engine."""

from __future__ import annotations

from typing import Any

from fastapi import FastAPI, HTTPException

from prism_scenario_engine import __version__
from prism_scenario_engine.config import ScenarioConfig
from prism_scenario_engine.journal import ScenarioJournal
from prism_scenario_engine.outcomes import load_weights
from prism_scenario_engine.sampler import ScenarioSampler


def create_app(config: ScenarioConfig | None = None) -> FastAPI:
    cfg = config or ScenarioConfig.from_env()
    app = FastAPI(
        title="PRISM Scenario Engine",
        version=__version__,
        description="Seeded, audited chaos source — ADR-005 synthetic labeling.",
    )
    app.state.config = cfg
    weights = load_weights(cfg.weights_path)
    journal = ScenarioJournal(cfg.journal_dir, cfg.scenario_id)
    sampler = ScenarioSampler(
        seed=cfg.seed,
        scenario_id=cfg.scenario_id,
        asset_ids=cfg.asset_ids,
        journal=journal,
        weights=weights,
    )
    app.state.sampler = sampler
    app.state.journal = journal

    @app.get("/health")
    def health() -> dict[str, Any]:
        return {
            "status": "ok",
            "service": "scenario-engine",
            "version": __version__,
            "seed": cfg.seed,
            "scenario_id": cfg.scenario_id,
            "tick": sampler.tick,
            "journal_path": str(journal.path),
            "synthetic_scenario": True,
        }

    @app.get("/v1/next-event")
    def next_event() -> dict[str, Any]:
        """Pull one sampled decision + optional payload for ingestion."""
        return sampler.next_event()

    @app.post("/v1/assets/{asset_id}/resume")
    def resume_asset(asset_id: str) -> dict[str, Any]:
        ok = sampler.resume_asset(asset_id)
        if not ok:
            raise HTTPException(status_code=404, detail=f"unknown asset_id: {asset_id}")
        return {"asset_id": asset_id, "stalled": False, "resumed": True}

    @app.get("/v1/status")
    def status() -> dict[str, Any]:
        stalled = {
            aid: state.stalled
            for aid, state in sampler._states.items()  # noqa: SLF001
        }
        return {
            "scenario_id": cfg.scenario_id,
            "seed": cfg.seed,
            "tick": sampler.tick,
            "stalled_assets": [aid for aid, flag in stalled.items() if flag],
            "journal_path": str(journal.path),
            "weights": weights,
        }

    return app
