"""PRISM CV finding contract — defect/anomaly detections on fleet imagery."""

from prism_cv_finding_schema.models import (
    ASSET_ID_PATTERN,
    FINDING_ID_PATTERN,
    FRAME_ID_PATTERN,
    BoundingBox,
    CvFinding,
    DefectClass,
)

__all__ = [
    "ASSET_ID_PATTERN",
    "FINDING_ID_PATTERN",
    "FRAME_ID_PATTERN",
    "BoundingBox",
    "CvFinding",
    "DefectClass",
]

__version__ = "0.1.0"
