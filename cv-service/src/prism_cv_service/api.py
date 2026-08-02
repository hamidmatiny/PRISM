"""FastAPI surface for the CV service."""

from __future__ import annotations

from typing import Annotated, Any

from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from pydantic import BaseModel, Field

from prism_cv_service.config import CvConfig
from prism_cv_service.detector import detector_info
from prism_cv_service.pipeline import CvPipeline


class DetectJsonRequest(BaseModel):
    asset_id: str = Field(..., examples=["PRISM-AST-001"])
    frame_ref: str = Field(..., examples=["frm_abcdef123456"])
    image_path: str = Field(..., description="Filesystem path visible to the service")


def create_app(config: CvConfig | None = None) -> FastAPI:
    cfg = config or CvConfig.from_env()
    pipeline = CvPipeline(cfg)
    app = FastAPI(title="PRISM CV Service", version="0.1.0")
    app.state.pipeline = pipeline
    app.state.config = cfg

    try:
        from prism_otel import instrument_fastapi

        instrument_fastapi(app, "cv-service")
    except ImportError:
        pass

    @app.get("/health")
    def health() -> dict[str, Any]:
        return {
            "status": "ok",
            "service": "cv-service",
            "model_id": cfg.model_id,
            "confidence_threshold": cfg.confidence_threshold,
            "providers": detector_info(pipeline.detector)["providers"],
            "review_pending": len(list(cfg.review_queue_dir.glob("*.json"))),
            "published": len(list(cfg.published_dir.glob("*.json"))),
        }

    @app.get("/v1/labels")
    def labels() -> dict[str, Any]:
        return {
            "model_id": cfg.model_id,
            "classes": detector_info(pipeline.detector)["classes"],
            "docs": "cv-service/docs/LABELS.md",
        }

    @app.get("/v1/review-queue")
    def review_queue() -> dict[str, Any]:
        items = pipeline.queue.list_pending()
        return {"count": len(items), "items": items}

    @app.post("/v1/detect")
    async def detect_upload(
        asset_id: Annotated[str, Form()],
        frame_ref: Annotated[str, Form()],
        file: Annotated[UploadFile, File()],
    ) -> dict[str, Any]:
        data = await file.read()
        if not data:
            raise HTTPException(status_code=400, detail="empty upload")
        try:
            return pipeline.detect_image(data, asset_id=asset_id, frame_ref=frame_ref)
        except Exception as exc:  # noqa: BLE001 — map to 400 for bad inputs
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.post("/v1/detect/path")
    def detect_path(body: DetectJsonRequest) -> dict[str, Any]:
        try:
            return pipeline.detect_image(
                body.image_path,
                asset_id=body.asset_id,
                frame_ref=body.frame_ref,
            )
        except Exception as exc:  # noqa: BLE001
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    return app
