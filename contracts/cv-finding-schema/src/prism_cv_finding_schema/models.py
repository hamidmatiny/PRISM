"""Defect/anomaly finding contract consumed by cv-service and control-plane."""

from __future__ import annotations

from datetime import UTC, datetime
from enum import StrEnum
from typing import Annotated, Any

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    StringConstraints,
    field_validator,
)

ASSET_ID_PATTERN = r"^PRISM-AST-\d{3}$"
FRAME_ID_PATTERN = r"^frm_[0-9a-f]{12}$"
FINDING_ID_PATTERN = r"^fnd_[0-9a-f]{12}$"

AssetId = Annotated[str, StringConstraints(pattern=ASSET_ID_PATTERN)]
FrameId = Annotated[str, StringConstraints(pattern=FRAME_ID_PATTERN)]
FindingId = Annotated[str, StringConstraints(pattern=FINDING_ID_PATTERN)]


class DefectClass(StrEnum):
    """Coherent fleet-asset defect label set (expanded in Phase 3 service docs)."""

    DENT = "dent"
    CRACK = "crack"
    TIRE_WEAR = "tire_wear"
    SENSOR_OBSTRUCTION = "sensor_obstruction"
    ANOMALY = "anomaly"


class BoundingBox(BaseModel):
    """Axis-aligned box in pixel space relative to the source frame."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    x: float = Field(..., ge=0.0, description="Left edge in pixels.")
    y: float = Field(..., ge=0.0, description="Top edge in pixels.")
    width: float = Field(..., gt=0.0)
    height: float = Field(..., gt=0.0)


class CvFinding(BaseModel):
    """One defect/anomaly detection tied to an asset and source frame."""

    model_config = ConfigDict(
        str_strip_whitespace=True,
        extra="forbid",
        validate_assignment=True,
    )

    schema_version: str = Field(default="1.0.0", pattern=r"^\d+\.\d+\.\d+$")
    finding_id: FindingId
    asset_id: AssetId
    frame_ref: FrameId = Field(..., description="Camera frame_id this finding refers to.")
    defect_class: DefectClass
    confidence: float = Field(..., ge=0.0, le=1.0)
    bounding_box: BoundingBox | None = None
    segmentation_mask_ref: str | None = Field(
        default=None,
        description="Optional URI for a segmentation mask object (s3:// or file://).",
    )
    reviewed: bool = Field(
        default=False,
        description="True after human review workflow approves/rejects/relabels.",
    )
    detected_at: datetime = Field(..., description="UTC detection time (timezone-aware).")
    model_id: str = Field(default="yolo-fleet-defects", min_length=1)

    @field_validator("detected_at", mode="before")
    @classmethod
    def normalize_detected_at(cls, value: Any) -> datetime:
        if value is None:
            raise ValueError("detected_at is required")
        if isinstance(value, str):
            value = datetime.fromisoformat(value.replace("Z", "+00:00"))
        if not isinstance(value, datetime):
            raise ValueError("detected_at must be a datetime")
        if value.tzinfo is None:
            raise ValueError("detected_at must be timezone-aware (UTC required)")
        return value.astimezone(UTC)

    @field_validator("segmentation_mask_ref")
    @classmethod
    def validate_mask_ref(cls, value: str | None) -> str | None:
        if value is None:
            return value
        if not (value.startswith("s3://") or value.startswith("file://")):
            raise ValueError("segmentation_mask_ref must start with s3:// or file://")
        return value

    def to_payload(self) -> dict[str, Any]:
        return self.model_dump(mode="json")
