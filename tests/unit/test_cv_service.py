"""CV service structural tests — schema validity & confidence bounds only."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest

from prism_cv_finding_schema import CvFinding, DefectClass
from prism_cv_service.config import CvConfig
from prism_cv_service.detector import YoloOnnxDetector, decode_yolo_head
from prism_cv_service.pipeline import CvPipeline
from prism_cv_service.preprocess import load_bgr_image, preprocess_bgr
from prism_cv_service.review_queue import ReviewQueue

ROOT = Path(__file__).resolve().parents[2]
CV_ROOT = ROOT / "cv-service"
FIXTURE_IMAGE = CV_ROOT / "fixtures" / "images" / "dent_sample.png"
MODEL = CV_ROOT / "models" / "yolo_fleet_defects_tiny.onnx"
LABELS = CV_ROOT / "models" / "labels.json"


@pytest.fixture
def cv_config(tmp_path: Path) -> CvConfig:
    return CvConfig(
        data_root=tmp_path / "data",
        model_path=MODEL,
        labels_path=LABELS,
        confidence_threshold=0.55,
        model_id="yolo-fleet-defects-tiny",
    )


def test_fixtures_exist() -> None:
    assert MODEL.is_file()
    assert LABELS.is_file()
    assert FIXTURE_IMAGE.is_file()
    images = list((CV_ROOT / "fixtures" / "images").glob("*.png"))
    assert len(images) >= 5


def test_preprocess_resize_denoise_contrast_shape() -> None:
    bgr = load_bgr_image(FIXTURE_IMAGE)
    batch, meta = preprocess_bgr(bgr, input_size=(320, 320))
    assert batch.shape == (1, 3, 320, 320)
    assert batch.dtype == np.float32
    assert 0.0 <= float(batch.min()) and float(batch.max()) <= 1.0
    assert meta["orig_width"] == 320
    assert meta["orig_height"] == 240


def test_onnx_detector_cpu_only_and_bounded_confidence(cv_config: CvConfig) -> None:
    detector = YoloOnnxDetector(
        cv_config.model_path,
        cv_config.labels_path,
        model_id=cv_config.model_id,
    )
    assert detector._session.get_providers() == ["CPUExecutionProvider"]
    bgr = load_bgr_image(FIXTURE_IMAGE)
    batch, meta = preprocess_bgr(bgr, input_size=cv_config.input_size)
    dets = detector.infer(batch, meta=meta, max_detections=10)
    assert dets, "expected at least one structural detection from tiny model"
    for det in dets:
        assert isinstance(det.defect_class, DefectClass)
        assert 0.0 <= det.confidence <= 1.0
        assert det.box.width > 0 and det.box.height > 0


def test_pipeline_findings_are_schema_valid(cv_config: CvConfig) -> None:
    pipeline = CvPipeline(cv_config)
    result = pipeline.detect_image(
        FIXTURE_IMAGE,
        asset_id="PRISM-AST-001",
        frame_ref="frm_abcdef123456",
    )
    assert result["published_count"] + result["review_count"] >= 1
    for item in result["published"] + result["review_queue"]:
        finding = CvFinding.model_validate(item["finding"])
        assert 0.0 <= finding.confidence <= 1.0
        assert finding.reviewed is False
        assert finding.model_id == "yolo-fleet-defects-tiny"


def test_low_confidence_routes_to_review_queue(tmp_path: Path) -> None:
    config = CvConfig(
        data_root=tmp_path / "data",
        model_path=MODEL,
        labels_path=LABELS,
        confidence_threshold=0.99,  # force review path
        model_id="yolo-fleet-defects-tiny",
    )
    pipeline = CvPipeline(config)
    result = pipeline.detect_image(
        FIXTURE_IMAGE,
        asset_id="PRISM-AST-002",
        frame_ref="frm_bbccddeeff00",
    )
    assert result["review_count"] >= 1
    assert result["published_count"] == 0
    pending = pipeline.queue.list_pending()
    assert len(pending) == result["review_count"]
    assert pending[0]["queue"] == "cv-human-review"
    CvFinding.model_validate(pending[0]["finding"])


def test_high_threshold_publish_path(tmp_path: Path) -> None:
    config = CvConfig(
        data_root=tmp_path / "data",
        model_path=MODEL,
        labels_path=LABELS,
        confidence_threshold=0.0,
        model_id="yolo-fleet-defects-tiny",
    )
    pipeline = CvPipeline(config)
    result = pipeline.detect_image(
        FIXTURE_IMAGE,
        asset_id="PRISM-AST-003",
        frame_ref="frm_001122334455",
    )
    assert result["published_count"] >= 1
    assert result["review_count"] == 0
    published_files = list(config.published_dir.glob("*.json"))
    assert published_files


def test_decode_rejects_bad_shapes() -> None:
    with pytest.raises(ValueError):
        decode_yolo_head(
            np.zeros((2, 2), dtype=np.float32),
            class_names=["dent"],
            meta={"orig_width": 10, "orig_height": 10},
            max_detections=1,
            score_floor=0.0,
        )


def test_review_queue_roundtrip(tmp_path: Path) -> None:
    q = ReviewQueue(tmp_path / "pending", tmp_path / "published")
    finding = CvFinding.model_validate(
        {
            "finding_id": "fnd_abcdef123456",
            "asset_id": "PRISM-AST-001",
            "frame_ref": "frm_abcdef123456",
            "defect_class": "dent",
            "confidence": 0.4,
            "bounding_box": {"x": 1, "y": 2, "width": 10, "height": 10},
            "reviewed": False,
            "detected_at": "2026-08-01T12:00:00Z",
            "model_id": "yolo-fleet-defects-tiny",
        }
    )
    q.enqueue_for_review(finding, reason="below threshold")
    assert len(q.list_pending()) == 1
