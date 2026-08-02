"""Pydantic contracts for fleet sensor pings and camera-frame metadata.

Field discipline mirrors hydra-data-factory ``schema_contract.py``: regex-validated
IDs, typed numeric ranges, and a required timezone-aware timestamp.
"""

from __future__ import annotations

import re
from datetime import UTC, datetime
from typing import Annotated, Any, Self

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    StringConstraints,
    field_validator,
    model_validator,
)

ASSET_ID_PATTERN = r"^PRISM-AST-\d{3}$"
DEVICE_ID_PATTERN = r"^PRISM-DEV-\d{3}$"
FRAME_ID_PATTERN = r"^frm_[0-9a-f]{12}$"

SPEED_MIN_MPH = 0.0
SPEED_MAX_MPH = 120.0
LATITUDE_MIN = -90.0
LATITUDE_MAX = 90.0
LONGITUDE_MIN = -180.0
LONGITUDE_MAX = 180.0
HEADING_MIN_DEG = 0.0
HEADING_MAX_DEG = 360.0

AssetId = Annotated[str, StringConstraints(pattern=ASSET_ID_PATTERN)]
DeviceId = Annotated[str, StringConstraints(pattern=DEVICE_ID_PATTERN)]
FrameId = Annotated[str, StringConstraints(pattern=FRAME_ID_PATTERN)]


def _require_aware_utc(value: datetime | str) -> datetime:
    if isinstance(value, str):
        value = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if value.tzinfo is None:
        raise ValueError("timestamp must be timezone-aware (UTC required)")
    return value.astimezone(UTC)


class SensorPing(BaseModel):
    """One sensor observation from a fleet asset device."""

    model_config = ConfigDict(
        str_strip_whitespace=True,
        extra="forbid",
        validate_assignment=True,
    )

    schema_version: str = Field(default="1.0.0", pattern=r"^\d+\.\d+\.\d+$")
    event_type: str = Field(default="sensor_ping", pattern=r"^sensor_ping$")
    asset_id: AssetId = Field(..., description="Fleet asset id, e.g. PRISM-AST-001.")
    device_id: DeviceId = Field(..., description="Telemetry device id, e.g. PRISM-DEV-001.")
    timestamp: datetime = Field(..., description="UTC observation time (timezone-aware).")
    speed_mph: float = Field(
        ...,
        ge=SPEED_MIN_MPH,
        le=SPEED_MAX_MPH,
        description="Ground speed within fleet operating envelope.",
    )
    latitude: float = Field(..., ge=LATITUDE_MIN, le=LATITUDE_MAX)
    longitude: float = Field(..., ge=LONGITUDE_MIN, le=LONGITUDE_MAX)
    heading_deg: float = Field(..., ge=HEADING_MIN_DEG, le=HEADING_MAX_DEG)
    odometer_km: float = Field(..., ge=0.0)
    fuel_level_pct: float | None = Field(default=None, ge=0.0, le=100.0)
    synthetic_scenario: bool = Field(
        default=False,
        description="True when emitted by scenario-engine (ADR-005); never live fleet.",
    )
    scenario_id: str | None = Field(
        default=None,
        min_length=1,
        max_length=128,
        description="Stable scenario run id when synthetic_scenario is true.",
    )
    scenario_outcome: str | None = Field(
        default=None,
        min_length=1,
        max_length=64,
        description="Optional scenario outcome tag (e.g. drift_signature).",
    )

    @field_validator("timestamp", mode="before")
    @classmethod
    def normalize_timestamp(cls, value: Any) -> datetime:
        if value is None:
            raise ValueError("timestamp is required")
        return _require_aware_utc(value)

    @model_validator(mode="after")
    def scenario_fields_consistent(self) -> Self:
        if self.synthetic_scenario and not self.scenario_id:
            raise ValueError("scenario_id is required when synthetic_scenario is true")
        if not self.synthetic_scenario and self.scenario_id is not None:
            raise ValueError("scenario_id must be omitted when synthetic_scenario is false")
        if self.scenario_outcome is not None and not self.synthetic_scenario:
            raise ValueError("scenario_outcome requires synthetic_scenario=true")
        return self

    def to_payload(self) -> dict[str, Any]:
        return self.model_dump(mode="json", exclude_none=True)


class CameraFrameMetadata(BaseModel):
    """Metadata for a captured fleet camera frame (imagery lives at storage_uri)."""

    model_config = ConfigDict(
        str_strip_whitespace=True,
        extra="forbid",
        validate_assignment=True,
    )

    schema_version: str = Field(default="1.0.0", pattern=r"^\d+\.\d+\.\d+$")
    event_type: str = Field(default="camera_frame", pattern=r"^camera_frame$")
    asset_id: AssetId
    device_id: DeviceId = Field(..., description="Camera device id.")
    frame_id: FrameId
    timestamp: datetime = Field(..., description="UTC capture time (timezone-aware).")
    storage_uri: str = Field(
        ...,
        min_length=1,
        description="Object URI for the frame bytes (s3:// or file://).",
    )
    content_type: str = Field(default="image/jpeg", pattern=r"^image/(jpeg|png|webp)$")
    width_px: int = Field(..., ge=1, le=16384)
    height_px: int = Field(..., ge=1, le=16384)
    capture_exposure_ms: float | None = Field(default=None, gt=0.0, le=60_000.0)
    synthetic_scenario: bool = Field(
        default=False,
        description="True when emitted by scenario-engine (ADR-005); never live fleet.",
    )
    scenario_id: str | None = Field(
        default=None,
        min_length=1,
        max_length=128,
        description="Stable scenario run id when synthetic_scenario is true.",
    )
    scenario_outcome: str | None = Field(
        default=None,
        min_length=1,
        max_length=64,
        description="Optional scenario outcome tag (e.g. cv_low_confidence).",
    )

    @field_validator("timestamp", mode="before")
    @classmethod
    def normalize_timestamp(cls, value: Any) -> datetime:
        if value is None:
            raise ValueError("timestamp is required")
        return _require_aware_utc(value)

    @field_validator("storage_uri")
    @classmethod
    def validate_storage_uri(cls, value: str) -> str:
        if not (value.startswith("s3://") or value.startswith("file://")):
            raise ValueError("storage_uri must start with s3:// or file://")
        return value

    @model_validator(mode="after")
    def frame_id_shape(self) -> Self:
        if not re.fullmatch(FRAME_ID_PATTERN, self.frame_id):
            raise ValueError(f"frame_id must match {FRAME_ID_PATTERN}")
        if self.synthetic_scenario and not self.scenario_id:
            raise ValueError("scenario_id is required when synthetic_scenario is true")
        if not self.synthetic_scenario and self.scenario_id is not None:
            raise ValueError("scenario_id must be omitted when synthetic_scenario is false")
        if self.scenario_outcome is not None and not self.synthetic_scenario:
            raise ValueError("scenario_outcome requires synthetic_scenario=true")
        return self

    def to_payload(self) -> dict[str, Any]:
        return self.model_dump(mode="json", exclude_none=True)
