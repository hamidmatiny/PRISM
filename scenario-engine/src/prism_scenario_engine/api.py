"""FastAPI surface for scenario-engine."""

from __future__ import annotations

import time
from typing import Any

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

from prism_scenario_engine import __version__
from prism_scenario_engine.config import ScenarioConfig
from prism_scenario_engine.journal import ScenarioJournal
from prism_scenario_engine.outcomes import load_weights, normalize_weights
from prism_scenario_engine.sampler import ScenarioSampler


class ResetRequest(BaseModel):
    seed: int = Field(..., description="New RNG seed; same seed always replays identically.")
    scenario_id: str | None = Field(
        default=None,
        description="Defaults to scn_{seed}_{unix_ts} so a fresh run never clobbers a prior "
        "run's audit journal for the same seed.",
    )
    weights: dict[str, float] | None = Field(
        default=None,
        description=(
            "Optional per-run outcome weights (Phase 17 drift-reseed). When omitted, "
            "the process-default weights stay in force. Values are normalized to sum 1.0."
        ),
    )


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
    app.state.run_weights = weights

    @app.get("/health")
    def health() -> dict[str, Any]:
        live = app.state.sampler
        return {
            "status": "ok",
            "service": "scenario-engine",
            "version": __version__,
            "seed": live.seed,
            "scenario_id": app.state.sampler.scenario_id,
            "tick": live.tick,
            "journal_path": str(app.state.journal.path),
            "synthetic_scenario": True,
        }

    @app.get("/v1/next-event")
    def next_event() -> dict[str, Any]:
        """Pull one sampled decision + optional payload for ingestion."""
        return app.state.sampler.next_event()

    @app.post("/v1/assets/{asset_id}/resume")
    def resume_asset(asset_id: str) -> dict[str, Any]:
        ok = app.state.sampler.resume_asset(asset_id)
        if not ok:
            raise HTTPException(status_code=404, detail=f"unknown asset_id: {asset_id}")
        return {"asset_id": asset_id, "stalled": False, "resumed": True}

    @app.get("/v1/status")
    def status() -> dict[str, Any]:
        live = app.state.sampler
        stalled = {
            aid: state.stalled
            for aid, state in live._states.items()  # noqa: SLF001
        }
        return {
            "scenario_id": app.state.sampler.scenario_id,
            "seed": live.seed,
            "tick": live.tick,
            "stalled_assets": [aid for aid, flag in stalled.items() if flag],
            "journal_path": str(app.state.journal.path),
            "weights": app.state.run_weights,
        }

    @app.post("/v1/reset")
    def reset(body: ResetRequest) -> dict[str, Any]:
        """Start a fresh seeded run in-process (Phase 15 cockpit scenario controls).

        Reconstructs the sampler against the new seed with a brand-new audit
        journal -- the prior run's journal file is left untouched, so replaying
        an old seed later is still byte-identical to the first time (Phase 12's
        reproducibility guarantee is unaffected by this endpoint's existence).
        """
        new_scenario_id = body.scenario_id or f"scn_{body.seed}_{int(time.time())}"
        new_journal = ScenarioJournal(cfg.journal_dir, new_scenario_id)
        run_weights = normalize_weights(body.weights) if body.weights is not None else weights
        new_sampler = ScenarioSampler(
            seed=body.seed,
            scenario_id=new_scenario_id,
            asset_ids=cfg.asset_ids,
            journal=new_journal,
            weights=run_weights,
        )
        app.state.sampler = new_sampler
        app.state.journal = new_journal
        app.state.run_weights = run_weights
        return {
            "seed": body.seed,
            "scenario_id": new_scenario_id,
            "tick": 0,
            "journal_path": str(new_journal.path),
            "weights": run_weights,
        }

    return app
