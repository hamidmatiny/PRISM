"""Mock fleet simulator — sensor pings + camera frame refs with failure injection.

Pattern adapted from hydra-data-factory ``generator.py``: kinematic evolution,
configurable failure_rate, and deliberate schema-breaking corruptions.
"""

from __future__ import annotations

import math
import random
import time
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any, Literal
from uuid import uuid4

from prism_telemetry_schema import CameraFrameMetadata, SensorPing

_DEFAULT_LATITUDE = 37.7749
_DEFAULT_LONGITUDE = -122.4194
_METERS_PER_DEGREE_LAT = 111_320.0

EventKind = Literal["sensor_ping", "camera_frame"]


@dataclass
class AssetState:
    latitude: float
    longitude: float
    speed_mph: float
    heading_deg: float
    odometer_km: float
    fuel_level_pct: float
    last_updated: float = field(default_factory=time.time)
    device_id: str = ""
    camera_device_id: str = ""


class FleetSimulator:
    """Emits schema-valid (or intentionally corrupt) fleet events."""

    def __init__(
        self,
        asset_ids: list[str] | tuple[str, ...],
        failure_rate: float = 0.0,
        *,
        seed: int | None = None,
        camera_ratio: float = 0.35,
    ) -> None:
        if not asset_ids:
            raise ValueError("asset_ids must contain at least one identifier")
        if not 0.0 <= failure_rate <= 1.0:
            raise ValueError("failure_rate must be between 0.0 and 1.0 inclusive")
        if not 0.0 <= camera_ratio <= 1.0:
            raise ValueError("camera_ratio must be between 0.0 and 1.0 inclusive")

        self.asset_ids = list(asset_ids)
        self.failure_rate = failure_rate
        self.camera_ratio = camera_ratio
        self._rng = random.Random(seed)
        self._states: dict[str, AssetState] = {}
        for index, asset_id in enumerate(self.asset_ids, start=1):
            self._states[asset_id] = AssetState(
                latitude=_DEFAULT_LATITUDE + self._rng.uniform(-0.03, 0.03),
                longitude=_DEFAULT_LONGITUDE + self._rng.uniform(-0.03, 0.03),
                speed_mph=self._rng.uniform(0.0, 40.0),
                heading_deg=self._rng.uniform(0.0, 360.0),
                odometer_km=self._rng.uniform(1_000.0, 80_000.0),
                fuel_level_pct=self._rng.uniform(20.0, 100.0),
                device_id=f"PRISM-DEV-{index:03d}",
                camera_device_id=f"PRISM-DEV-{index + 100:03d}",
            )

    def generate_event(self) -> tuple[EventKind, dict[str, Any]]:
        """Generate one event; may be corrupted when failure_rate triggers."""
        asset_id = self._rng.choice(self.asset_ids)
        kind: EventKind = (
            "camera_frame" if self._rng.random() < self.camera_ratio else "sensor_ping"
        )
        if kind == "sensor_ping":
            payload = self._generate_sensor_ping(asset_id)
        else:
            payload = self._generate_camera_frame(asset_id)

        if self._rng.random() < self.failure_rate:
            payload = self._corrupt_payload(kind, payload, asset_id)
        return kind, payload

    def _generate_sensor_ping(self, asset_id: str) -> dict[str, Any]:
        state = self._states[asset_id]
        now = time.time()
        elapsed = max(now - state.last_updated, 0.001)
        state.last_updated = now
        self._evolve_kinematics(state, elapsed)

        ping = SensorPing(
            asset_id=asset_id,
            device_id=state.device_id,
            timestamp=datetime.fromtimestamp(now, tz=UTC),
            speed_mph=round(state.speed_mph, 2),
            latitude=round(state.latitude, 7),
            longitude=round(state.longitude, 7),
            heading_deg=round(state.heading_deg % 360.0, 2),
            odometer_km=round(state.odometer_km, 2),
            fuel_level_pct=round(state.fuel_level_pct, 2),
        )
        return ping.to_payload()

    def _generate_camera_frame(self, asset_id: str) -> dict[str, Any]:
        state = self._states[asset_id]
        now = time.time()
        frame_id = f"frm_{uuid4().hex[:12]}"
        day = datetime.fromtimestamp(now, tz=UTC).strftime("%Y-%m-%d")
        storage_uri = (
            f"file://bronze/raw_frames/dt={day}/device={state.camera_device_id}/{frame_id}.jpg"
        )
        frame = CameraFrameMetadata(
            asset_id=asset_id,
            device_id=state.camera_device_id,
            frame_id=frame_id,
            timestamp=datetime.fromtimestamp(now, tz=UTC),
            storage_uri=storage_uri,
            content_type="image/jpeg",
            width_px=1920,
            height_px=1080,
            capture_exposure_ms=round(self._rng.uniform(1.0, 20.0), 2),
        )
        return frame.to_payload()

    def _evolve_kinematics(self, state: AssetState, elapsed_seconds: float) -> None:
        target_speed = state.speed_mph + self._rng.uniform(-8.0, 8.0)
        target_speed = max(0.0, min(target_speed, 75.0))
        state.speed_mph += (target_speed - state.speed_mph) * min(elapsed_seconds * 0.5, 1.0)

        if state.speed_mph < 2.0 and self._rng.random() < 0.15:
            state.heading_deg = (state.heading_deg + self._rng.uniform(-45.0, 45.0)) % 360.0

        speed_mps = state.speed_mph * 0.44704
        distance_m = speed_mps * elapsed_seconds
        heading_rad = math.radians(state.heading_deg)
        delta_lat = (distance_m * math.cos(heading_rad)) / _METERS_PER_DEGREE_LAT
        delta_lon = (distance_m * math.sin(heading_rad)) / (
            _METERS_PER_DEGREE_LAT * max(math.cos(math.radians(state.latitude)), 1e-6)
        )
        state.latitude += delta_lat
        state.longitude += delta_lon
        state.odometer_km += distance_m / 1000.0
        state.fuel_level_pct = max(0.0, state.fuel_level_pct - elapsed_seconds * 0.001)

    def _corrupt_payload(
        self,
        kind: EventKind,
        payload: dict[str, Any],
        asset_id: str,
    ) -> dict[str, Any]:
        strategies = (
            "drop_asset_id",
            "null_timestamp",
            "invalid_speed_or_size",
            "bad_id_pattern",
            "malformed_uri",
        )
        strategy = self._rng.choice(strategies)
        corrupted = dict(payload)
        corrupted["_corruption"] = strategy

        if strategy == "drop_asset_id":
            corrupted.pop("asset_id", None)
        elif strategy == "null_timestamp":
            corrupted["timestamp"] = None
        elif strategy == "invalid_speed_or_size":
            if kind == "sensor_ping":
                corrupted["speed_mph"] = "NOT_A_NUMBER"
            else:
                corrupted["width_px"] = -1
        elif strategy == "bad_id_pattern":
            corrupted["asset_id"] = f"BAD-{asset_id}"
        elif strategy == "malformed_uri" and kind == "camera_frame":
            corrupted["storage_uri"] = "http://not-allowed.example/frame.jpg"
        elif strategy == "malformed_uri":
            corrupted["latitude"] = 999.0

        return corrupted
