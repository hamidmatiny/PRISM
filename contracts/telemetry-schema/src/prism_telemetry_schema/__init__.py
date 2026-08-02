"""PRISM telemetry contracts — sensor pings and camera-frame metadata."""

from prism_telemetry_schema.models import (
    ASSET_ID_PATTERN,
    DEVICE_ID_PATTERN,
    FRAME_ID_PATTERN,
    CameraFrameMetadata,
    SensorPing,
)

__all__ = [
    "ASSET_ID_PATTERN",
    "DEVICE_ID_PATTERN",
    "FRAME_ID_PATTERN",
    "CameraFrameMetadata",
    "SensorPing",
]

__version__ = "0.1.0"
