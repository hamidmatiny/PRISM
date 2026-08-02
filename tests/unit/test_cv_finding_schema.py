"""CV finding schema happy-path and rejection tests."""

from __future__ import annotations

import json
from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from prism_cv_finding_schema import BoundingBox, CvFinding, DefectClass
from prism_cv_finding_schema.export import export_json_schemas, schema_dir


def _valid_finding(**overrides: object) -> dict:
    base = {
        "finding_id": "fnd_abcdef123456",
        "asset_id": "PRISM-AST-001",
        "frame_ref": "frm_abcdef123456",
        "defect_class": "dent",
        "confidence": 0.87,
        "bounding_box": {"x": 10.0, "y": 20.0, "width": 64.0, "height": 48.0},
        "segmentation_mask_ref": "s3://prism-raw/masks/fnd_abcdef123456.png",
        "reviewed": False,
        "detected_at": "2026-08-01T16:00:00Z",
        "model_id": "yolo-fleet-defects",
    }
    base.update(overrides)
    return base


def test_cv_finding_happy_path() -> None:
    finding = CvFinding.model_validate(_valid_finding())
    assert finding.defect_class is DefectClass.DENT
    assert finding.reviewed is False
    assert isinstance(finding.bounding_box, BoundingBox)
    assert finding.detected_at == datetime(2026, 8, 1, 16, 0, tzinfo=UTC)


@pytest.mark.parametrize(
    "overrides",
    [
        {"confidence": 1.5},
        {"confidence": -0.01},
        {"defect_class": "scratch"},
        {"asset_id": "AST-001"},
        {"frame_ref": "frame-1"},
        {"finding_id": "finding-1"},
        {"detected_at": None},
        {"segmentation_mask_ref": "https://example.com/mask.png"},
        {"bounding_box": {"x": 0, "y": 0, "width": 0, "height": 10}},
    ],
)
def test_cv_finding_rejection_paths(overrides: dict) -> None:
    with pytest.raises(ValidationError):
        CvFinding.model_validate(_valid_finding(**overrides))


def test_json_schema_export_matches_committed_files() -> None:
    generated = export_json_schemas(write=False)
    for name, schema in generated.items():
        path = schema_dir() / name
        assert path.is_file()
        committed = json.loads(path.read_text(encoding="utf-8"))
        assert committed == schema
