"""FastAPI surface for incident-engine."""

from __future__ import annotations

from typing import Any

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

from prism_incident_engine.config import IncidentConfig
from prism_incident_engine.journal import IncidentJournal
from prism_incident_engine.opa_client import build_policy_engine
from prism_incident_engine.store import IncidentStore
from prism_incident_engine.trip_policies import load_policies
from prism_incident_engine.webhook import WebhookSender


class ObservationRequest(BaseModel):
    asset_id: str = Field(..., examples=["PRISM-AST-001"])
    kind: str = Field(
        ...,
        description="ingestion_accepted | ingestion_quarantined | qa_pass | qa_fail | drift",
    )
    detail: dict[str, Any] = Field(default_factory=dict)


def create_app(config: IncidentConfig | None = None) -> FastAPI:
    cfg = config or IncidentConfig.from_env()
    policies = load_policies(cfg.policies_path)
    journal = IncidentJournal(cfg.journal_path)
    webhook = WebhookSender(cfg.webhook_inbox_path, receiver_url=f"http://127.0.0.1:{cfg.port}")
    policy_engine = build_policy_engine(
        opa_url=cfg.opa_url,
        policy_dir=cfg.opa_policy_dir,
        opa_bin=cfg.opa_bin,
    )
    store = IncidentStore(policies, journal, webhook, policy_engine)

    app = FastAPI(
        title="PRISM Incident Engine",
        version="0.18.0",
        description=(
            "Per-asset circuit breaker: closed -> open -> half_open. "
            "Trip thresholds evaluated by OPA/Rego (Phase 18)."
        ),
    )
    app.state.config = cfg
    app.state.store = store
    app.state.policies = policies
    app.state.policy_engine = policy_engine

    try:
        from prism_otel import instrument_fastapi

        instrument_fastapi(app, "incident-engine")
    except ImportError:
        pass

    @app.get("/health")
    def health() -> dict[str, Any]:
        breakers = store.all_breakers()
        engine_ready = policy_engine.ready()
        return {
            "status": "ok",
            "service": "incident-engine",
            "version": "0.18.0",
            "assets_tracked": len(breakers),
            "open_breakers": sum(1 for b in breakers if b["state"] == "open"),
            "half_open_breakers": sum(1 for b in breakers if b["state"] == "half_open"),
            "policy_engine": {
                "ready": engine_ready,
                "mode": policy_engine.mode,
                "policy_dir": policy_engine.policy_dir,
                "source_of_truth": "rego",
            },
            "fsm": {
                "quarantine_rate_window": policies.quarantine_rate_window,
                "cooldown_seconds": policies.cooldown_seconds,
            },
        }

    @app.post("/v1/observations")
    def observe(body: ObservationRequest) -> dict[str, Any]:
        valid_kinds = {"ingestion_accepted", "ingestion_quarantined", "qa_pass", "qa_fail", "drift"}
        if body.kind not in valid_kinds:
            raise HTTPException(
                status_code=400,
                detail=f"unknown kind {body.kind!r}, expected one of {sorted(valid_kinds)}",
            )
        return store.record_observation(body.asset_id, body.kind, body.detail)  # type: ignore[arg-type]

    @app.get("/breakers")
    def breakers() -> dict[str, Any]:
        items = store.all_breakers()
        return {"count": len(items), "breakers": items}

    @app.get("/breakers/{asset_id}")
    def breaker_detail(asset_id: str) -> dict[str, Any]:
        store.refresh_breaker_cooldown(store.breaker(asset_id))
        return store.breaker(asset_id).to_dict()

    @app.get("/incidents")
    def incidents(status: str | None = None) -> dict[str, Any]:
        if status is not None and status not in {"open", "acknowledged", "resolved"}:
            raise HTTPException(status_code=400, detail="status must be open|acknowledged|resolved")
        items = store.incidents(status)
        return {"count": len(items), "incidents": items}

    @app.get("/incidents/{incident_id}")
    def incident_detail(incident_id: str) -> dict[str, Any]:
        incident = store.incident(incident_id)
        if incident is None:
            raise HTTPException(status_code=404, detail=f"unknown incident_id {incident_id!r}")
        return incident.to_dict()

    @app.post("/incidents/{incident_id}/acknowledge")
    def acknowledge(incident_id: str) -> dict[str, Any]:
        incident = store.acknowledge(incident_id)
        if incident is None:
            raise HTTPException(status_code=404, detail=f"unknown incident_id {incident_id!r}")
        return incident.to_dict()

    @app.post("/incidents/{incident_id}/resolve")
    def resolve(incident_id: str) -> dict[str, Any]:
        incident = store.resolve(incident_id)
        if incident is None:
            raise HTTPException(status_code=404, detail=f"unknown incident_id {incident_id!r}")
        return incident.to_dict()

    @app.post("/v1/webhook-test/receive")
    def webhook_receive(payload: dict[str, Any]) -> dict[str, Any]:
        return webhook.deliver(payload)

    @app.get("/v1/webhook-test/inbox")
    def webhook_inbox() -> dict[str, Any]:
        items = webhook.inbox()
        return {"count": len(items), "items": items}

    @app.get("/v1/journal")
    def journal_tail(limit: int = 100) -> dict[str, Any]:
        items = journal.tail(limit)
        return {"count": len(items), "entries": items}

    return app
