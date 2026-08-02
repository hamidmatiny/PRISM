"""ONNX Runtime YOLO-family detector (CPUExecutionProvider only — ADR-001)."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np
import onnxruntime as ort

from prism_cv_finding_schema import BoundingBox, DefectClass


@dataclass(frozen=True)
class RawDetection:
    defect_class: DefectClass
    confidence: float
    box: BoundingBox


class YoloOnnxDetector:
    """Decode a compact YOLO-style head: output ``[1, 4+C, A]``."""

    def __init__(self, model_path: Path, labels_path: Path, *, model_id: str) -> None:
        if not model_path.is_file():
            raise FileNotFoundError(f"ONNX model missing: {model_path}")
        available = ort.get_available_providers()
        if "CPUExecutionProvider" not in available:
            raise RuntimeError("CPUExecutionProvider required (ADR-001: no GPU CI)")
        # Refuse CUDA/Tensorrt providers even if present.
        self._session = ort.InferenceSession(
            str(model_path),
            providers=["CPUExecutionProvider"],
        )
        labels = json.loads(labels_path.read_text(encoding="utf-8"))
        self.class_names = [c["name"] for c in labels["classes"]]
        self.model_id = model_id
        self.input_name = self._session.get_inputs()[0].name

    def infer(
        self,
        batch: np.ndarray,
        *,
        meta: dict[str, float | int],
        max_detections: int = 20,
        score_floor: float = 0.05,
    ) -> list[RawDetection]:
        outputs = self._session.run(None, {self.input_name: batch})
        raw = outputs[0]
        return decode_yolo_head(
            raw,
            class_names=self.class_names,
            meta=meta,
            max_detections=max_detections,
            score_floor=score_floor,
        )


def decode_yolo_head(
    raw: np.ndarray,
    *,
    class_names: list[str],
    meta: dict[str, float | int],
    max_detections: int,
    score_floor: float,
) -> list[RawDetection]:
    """
    Decode ``[1, 4+C, A]`` (cx,cy,w,h normalized + class scores).

    Structural decoder only — no accuracy claims.
    """
    if raw.ndim != 3:
        raise ValueError(f"unexpected ONNX output rank: {raw.shape}")
    # Accept [1,C,A] or [1,A,C]
    channel_major = raw.shape[1] == 4 + len(class_names)
    anchor_major = raw.shape[2] == 4 + len(class_names)
    if not channel_major and not anchor_major:
        raise ValueError(f"unexpected ONNX output shape: {raw.shape}")
    tensor = raw[0]
    anchors = tensor.shape[1] if channel_major else tensor.shape[0]

    orig_w = float(meta["orig_width"])
    orig_h = float(meta["orig_height"])
    detections: list[RawDetection] = []

    for i in range(anchors):
        col = tensor[:, i] if channel_major else tensor[i, :]
        cx, cy, bw, bh = (float(col[0]), float(col[1]), float(col[2]), float(col[3]))
        class_scores = col[4 : 4 + len(class_names)]
        class_id = int(np.argmax(class_scores))
        confidence = float(np.clip(class_scores[class_id], 0.0, 1.0))
        if confidence < score_floor:
            continue
        # cx,cy,w,h are normalized to input letterbox; map to original pixels.
        x = max(0.0, (cx - bw / 2.0) * orig_w)
        y = max(0.0, (cy - bh / 2.0) * orig_h)
        width = max(1.0, bw * orig_w)
        height = max(1.0, bh * orig_h)
        # Clip box to frame.
        width = min(width, orig_w - x)
        height = min(height, orig_h - y)
        if width <= 0 or height <= 0:
            continue
        name = class_names[class_id]
        detections.append(
            RawDetection(
                defect_class=DefectClass(name),
                confidence=confidence,
                box=BoundingBox(x=x, y=y, width=width, height=height),
            )
        )

    detections.sort(key=lambda d: d.confidence, reverse=True)
    return detections[:max_detections]


def detector_info(detector: YoloOnnxDetector) -> dict[str, Any]:
    return {
        "model_id": detector.model_id,
        "classes": detector.class_names,
        "providers": detector._session.get_providers(),
    }
