"""Detect → schema-validate → publish or review-queue by confidence."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

import numpy as np

from prism_cv_finding_schema import CvFinding
from prism_cv_service.config import CvConfig
from prism_cv_service.detector import YoloOnnxDetector
from prism_cv_service.incident_client import (
    breaker_is_open,
    report_qa_observation,
)
from prism_cv_service.preprocess import load_bgr_image, preprocess_bgr
from prism_cv_service.review_queue import ReviewQueue


class CvPipeline:
    def __init__(self, config: CvConfig) -> None:
        self.config = config
        self.detector = YoloOnnxDetector(
            config.model_path,
            config.labels_path,
            model_id=config.model_id,
        )
        self.queue = ReviewQueue(config.review_queue_dir, config.published_dir)

    def detect_image(
        self,
        image: str | bytes | np.ndarray,
        *,
        asset_id: str,
        frame_ref: str,
    ) -> dict[str, Any]:
        if isinstance(image, np.ndarray):
            bgr = image
        else:
            bgr = load_bgr_image(image)

        batch, meta = preprocess_bgr(bgr, input_size=self.config.input_size)
        raw = self.detector.infer(
            batch,
            meta=meta,
            max_detections=self.config.max_detections,
        )

        published: list[dict[str, Any]] = []
        review: list[dict[str, Any]] = []
        threshold = self.config.confidence_threshold
        now = datetime.now(tz=UTC)
        # Checked once per detect_image call (not once per detection) -- a single
        # frame's findings all share the same source-health verdict.
        forced_review = breaker_is_open(self.config.incident_engine_url, asset_id)

        for det in raw:
            finding = CvFinding(
                finding_id=f"fnd_{uuid4().hex[:12]}",
                asset_id=asset_id,
                frame_ref=frame_ref,
                defect_class=det.defect_class,
                confidence=det.confidence,
                bounding_box=det.box,
                reviewed=False,
                detected_at=now,
                model_id=self.config.model_id,
            )
            # Re-validate via model_validate for structural guarantee.
            finding = CvFinding.model_validate(finding.to_payload())

            low_confidence = finding.confidence < threshold
            if low_confidence or forced_review:
                reason = (
                    f"confidence {finding.confidence:.4f} < threshold {threshold}"
                    if low_confidence
                    else f"source breaker open for {asset_id} -- "
                    "routed to review regardless of confidence"
                )
                path = self.queue.enqueue_for_review(finding, reason=reason)
                review.append({"finding": finding.to_payload(), "queue_path": str(path)})
                report_qa_observation(
                    self.config.incident_engine_url, asset_id=asset_id, passed=False
                )
            else:
                path = self.queue.publish(finding)
                published.append({"finding": finding.to_payload(), "path": str(path)})
                report_qa_observation(
                    self.config.incident_engine_url, asset_id=asset_id, passed=True
                )

        return {
            "asset_id": asset_id,
            "source_breaker_open": forced_review,
            "frame_ref": frame_ref,
            "model_id": self.config.model_id,
            "confidence_threshold": threshold,
            "published_count": len(published),
            "review_count": len(review),
            "published": published,
            "review_queue": review,
        }
