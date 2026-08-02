"""Telemetry schema happy-path and rejection tests."""

from __future__ import annotations

import json
from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from prism_telemetry_schema import CameraFrameMetadata, SensorPing
from prism_telemetry_schema.export import export_json_schemas, schema_dir


def _valid_ping(**overrides: object) -> dict:
    base = {
        "asset_id": "PRISM-AST-001",
        "device_id": "PRISM-DEV-001",
        "timestamp": "2026-08-01T15:30:00Z",
        "speed_mph": 32.5,
        "latitude": 37.7749,
        "longitude": -122.4194,
        "heading_deg": 90.0,
        "odometer_km": 12000.0,
        "fuel_level_pct": 55.0,
    }
    base.update(overrides)
    return base


def _valid_frame(**overrides: object) -> dict:
    base = {
        "asset_id": "PRISM-AST-002",
        "device_id": "PRISM-DEV-101",
        "frame_id": "frm_abcdef123456",
        "timestamp": "2026-08-01T15:30:01+00:00",
        "storage_uri": "s3://prism-raw/frames/frm_abcdef123456.jpg",
        "content_type": "image/jpeg",
        "width_px": 1920,
        "height_px": 1080,
    }
    base.update(overrides)
    return base


def test_sensor_ping_happy_path() -> None:
    ping = SensorPing.model_validate(_valid_ping())
    assert ping.asset_id == "PRISM-AST-001"
    assert ping.timestamp.tzinfo is not None
    assert ping.timestamp == datetime(2026, 8, 1, 15, 30, tzinfo=UTC)


def test_camera_frame_happy_path() -> None:
    frame = CameraFrameMetadata.model_validate(_valid_frame())
    assert frame.frame_id.startswith("frm_")
    assert frame.storage_uri.startswith("s3://")


@pytest.mark.parametrize(
    "overrides",
    [
        {"asset_id": "BAD-ID"},
        {"timestamp": None},
        {"speed_mph": 999.0},
        {"latitude": -100.0},
        {"device_id": "DEV-1"},
    ],
)
def test_sensor_ping_rejection_paths(overrides: dict) -> None:
    with pytest.raises(ValidationError):
        SensorPing.model_validate(_valid_ping(**overrides))


@pytest.mark.parametrize(
    "overrides",
    [
        {"frame_id": "not-a-frame"},
        {"storage_uri": "http://example.com/x.jpg"},
        {"width_px": 0},
        {"timestamp": "2026-08-01T15:30:01"},  # naive / no tz
        {"asset_id": "PRISM-AST-1"},  # wrong digit count
    ],
)
def test_camera_frame_rejection_paths(overrides: dict) -> None:
    with pytest.raises(ValidationError):
        CameraFrameMetadata.model_validate(_valid_frame(**overrides))


def test_naive_timestamp_rejected() -> None:
    with pytest.raises(ValidationError):
        SensorPing.model_validate(_valid_ping(timestamp=datetime(2026, 8, 1, 15, 30)))


def test_json_schema_export_matches_committed_files() -> None:
    generated = export_json_schemas(write=False)
    for name, schema in generated.items():
        path = schema_dir() / name
        assert path.is_file(), f"missing committed schema {path}"
        committed = json.loads(path.read_text(encoding="utf-8"))
        assert committed == schema
