"""FastAPI surface for drift-monitor (Phase 16)."""

from __future__ import annotations

from typing import Any, Literal

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

from prism_drift_monitor.config import DriftConfig
from prism_drift_monitor.store import DriftStore


class ObserveRequest(BaseModel):
    asset_id: str = Field(..., examples=["PRISM-AST-001"])
    group: Literal["telemetry_numeric", "cv_geometry"] = Field(
        ..., description="telemetry_numeric (SensorPing numerics) | cv_geometry (CvFinding)"
    )
    payload: dict[str, Any] = Field(
        ..., description="Validated SensorPing or CvFinding payload (to_payload() output)."
    )
    synthetic_scenario: bool = Field(
        default=False,
        description=(
            "True for scenario-engine-originated events. Never counted toward the "
            "real baseline (ADR-005 / Argus ADR-007); fully eligible for the "
            "comparison window."
        ),
    )


def create_app(config: DriftConfig | None = None) -> FastAPI:
    cfg = config or DriftConfig.from_env()
    store = DriftStore(cfg)

    app = FastAPI(
        title="PRISM Drift Monitor",
        version="0.16.0",
        description=(
            "Honest-baseline drift detection (Phase 16): KS test on numeric "
            "telemetry features, centroid distance + KS-on-norms on a real CV "
            "finding feature vector. No test ever runs before a real, "
            "non-synthetic baseline exists (ADR-005)."
        ),
    )
    app.state.config = cfg
    app.state.store = store

    try:
        from prism_otel import instrument_fastapi

        instrument_fastapi(app, "drift-monitor")
    except ImportError:
        pass

    @app.get("/health")
    def health() -> dict[str, Any]:
        return {
            "status": "ok",
            "service": "drift-monitor",
            "version": "0.16.0",
            "baseline_ready": store.baseline_ready(),
            "config": {
                "baseline_samples": cfg.baseline_samples,
                "window_size": cfg.window_size,
                "ks_alpha": cfg.ks_alpha,
                "centroid_z": cfg.centroid_z,
            },
            "assets": store.status(),
        }

    @app.get("/v1/status")
    def status() -> dict[str, Any]:
        return {"baseline_ready": store.baseline_ready(), "assets": store.status()}

    @app.post("/v1/observe")
    def observe(body: ObserveRequest) -> dict[str, Any]:
        if body.group == "telemetry_numeric":
            result = store.observe_telemetry(
                body.asset_id, body.payload, synthetic=body.synthetic_scenario
            )
        elif body.group == "cv_geometry":
            result = store.observe_cv_finding(
                body.asset_id, body.payload, synthetic=body.synthetic_scenario
            )
        else:  # unreachable given Literal, kept for defensiveness
            raise HTTPException(status_code=400, detail=f"unknown group {body.group!r}")
        if result is None:
            return {"detection_ran": False, "asset_id": body.asset_id, "group": body.group}
        return {
            "detection_ran": True,
            "asset_id": result.asset_id,
            "group": result.group,
            "drifted_feature_count": result.drifted_feature_count,
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
        }

    return app
