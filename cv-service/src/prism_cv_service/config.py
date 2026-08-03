"""Runtime configuration for the CV service (CPU-only, ADR-001)."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

# Repo-relative defaults when running from a checkout / installed package sibling.
_REPO_MODELS = Path(__file__).resolve().parents[2] / "models"


@dataclass(frozen=True)
class CvConfig:
    host: str = "0.0.0.0"
    port: int = 9102
    data_root: Path = Path(".data")
    model_path: Path = _REPO_MODELS / "yolo_fleet_defects_tiny.onnx"
    labels_path: Path = _REPO_MODELS / "labels.json"
    confidence_threshold: float = 0.55
    input_size: tuple[int, int] = (320, 320)
    model_id: str = "yolo-fleet-defects-tiny"
    max_detections: int = 20
    incident_engine_url: str = "http://127.0.0.1:9108"
    drift_monitor_url: str = "http://127.0.0.1:9109"

    @property
    def review_queue_dir(self) -> Path:
        return self.data_root / "cv-review-queue" / "pending"

    @property
    def published_dir(self) -> Path:
        return self.data_root / "cv-findings" / "published"

    @classmethod
    def from_env(cls) -> CvConfig:
        size = int(os.getenv("PRISM_CV_INPUT_SIZE", "320"))
        return cls(
            host=os.getenv("PRISM_CV_HOST", "0.0.0.0"),
            port=int(os.getenv("PRISM_CV_SERVICE_PORT", "9102")),
            data_root=Path(os.getenv("PRISM_DATA_ROOT", ".data")),
            model_path=Path(
                os.getenv(
                    "PRISM_CV_MODEL_PATH",
                    str(_REPO_MODELS / "yolo_fleet_defects_tiny.onnx"),
                )
            ),
            labels_path=Path(os.getenv("PRISM_CV_LABELS_PATH", str(_REPO_MODELS / "labels.json"))),
            confidence_threshold=float(os.getenv("PRISM_CV_CONFIDENCE_THRESHOLD", "0.55")),
            input_size=(size, size),
            model_id=os.getenv("PRISM_CV_MODEL_ID", "yolo-fleet-defects-tiny"),
            max_detections=int(os.getenv("PRISM_CV_MAX_DETECTIONS", "20")),
            incident_engine_url=os.getenv("PRISM_INCIDENT_ENGINE_URL", "http://127.0.0.1:9108"),
            drift_monitor_url=os.getenv("PRISM_DRIFT_MONITOR_URL", "http://127.0.0.1:9109"),
        )
