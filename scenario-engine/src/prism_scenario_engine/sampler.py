"""Seeded per-asset outcome sampler + deterministic event payloads."""

from __future__ import annotations

import math
import random
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from typing import Any

from prism_scenario_engine.journal import JournalEntry, ScenarioJournal
from prism_scenario_engine.outcomes import ALL_OUTCOMES, Outcome, load_weights
from prism_telemetry_schema import CameraFrameMetadata, SensorPing

# Fixed epoch so two runs with the same seed produce identical timestamps.
_SCENARIO_EPOCH = datetime(2026, 8, 1, 12, 0, 0, tzinfo=UTC)
_DEFAULT_LATITUDE = 37.7749
_DEFAULT_LONGITUDE = -122.4194


@dataclass
class _AssetState:
    latitude: float
    longitude: float
    speed_mph: float
    heading_deg: float
    odometer_km: float
    fuel_level_pct: float
    device_id: str
    camera_device_id: str
    stalled: bool = False


@dataclass
class ScenarioSampler:
    """Samples outcomes and builds payloads; journal records every decision."""

    seed: int
    scenario_id: str
    asset_ids: tuple[str, ...]
    journal: ScenarioJournal
    weights: dict[Outcome, float] = field(default_factory=dict)
    tick: int = 0
    _rng: random.Random = field(init=False, repr=False)
    _states: dict[str, _AssetState] = field(init=False, repr=False)
    _outcome_names: list[Outcome] = field(init=False, repr=False)
    _outcome_weights: list[float] = field(init=False, repr=False)

    def __post_init__(self) -> None:
        if not self.weights:
            self.weights = load_weights()
        self._rng = random.Random(self.seed)
        self._outcome_names = list(ALL_OUTCOMES)
        self._outcome_weights = [self.weights[name] for name in self._outcome_names]
        self._states = {}
        for index, asset_id in enumerate(self.asset_ids, start=1):
            self._states[asset_id] = _AssetState(
                latitude=_DEFAULT_LATITUDE + self._rng.uniform(-0.03, 0.03),
                longitude=_DEFAULT_LONGITUDE + self._rng.uniform(-0.03, 0.03),
                speed_mph=self._rng.uniform(5.0, 35.0),
                heading_deg=self._rng.uniform(0.0, 360.0),
                odometer_km=self._rng.uniform(1_000.0, 80_000.0),
                fuel_level_pct=self._rng.uniform(20.0, 100.0),
                device_id=f"PRISM-DEV-{index:03d}",
                camera_device_id=f"PRISM-DEV-{index + 100:03d}",
            )

    def resume_asset(self, asset_id: str) -> bool:
        state = self._states.get(asset_id)
        if state is None:
            return False
        state.stalled = False
        return True

    def next_event(self) -> dict[str, Any]:
        """Advance one tick; return envelope for ingestion (may be skip)."""
        self.tick += 1
        asset_id = self.asset_ids[(self.tick - 1) % len(self.asset_ids)]
        outcome = self._sample_outcome()
        state = self._states[asset_id]

        if outcome == "stalled_source":
            state.stalled = True

        if state.stalled and outcome != "stalled_source":
            # Still journal the sampled decision, but do not emit.
            self.journal.append(
                JournalEntry(
                    scenario_id=self.scenario_id,
                    seed=self.seed,
                    tick=self.tick,
                    asset_id=asset_id,
                    outcome=outcome,
                    event_id=None,
                    kind=None,
                    emitted=False,
                )
            )
            return {
                "skip": True,
                "reason": "stalled_source",
                "tick": self.tick,
                "asset_id": asset_id,
                "outcome": outcome,
                "scenario_id": self.scenario_id,
            }

        if outcome == "stalled_source":
            self.journal.append(
                JournalEntry(
                    scenario_id=self.scenario_id,
                    seed=self.seed,
                    tick=self.tick,
                    asset_id=asset_id,
                    outcome=outcome,
                    event_id=None,
                    kind=None,
                    emitted=False,
                )
            )
            return {
                "skip": True,
                "reason": "stalled_source",
                "tick": self.tick,
                "asset_id": asset_id,
                "outcome": outcome,
                "scenario_id": self.scenario_id,
            }

        kind, payload, event_id = self._build_payload(asset_id, outcome)
        self.journal.append(
            JournalEntry(
                scenario_id=self.scenario_id,
                seed=self.seed,
                tick=self.tick,
                asset_id=asset_id,
                outcome=outcome,
                event_id=event_id,
                kind=kind,
                emitted=True,
            )
        )
        return {
            "skip": False,
            "tick": self.tick,
            "asset_id": asset_id,
            "outcome": outcome,
            "scenario_id": self.scenario_id,
            "kind": kind,
            "event_id": event_id,
            "payload": payload,
        }

    def _sample_outcome(self) -> Outcome:
        return self._rng.choices(self._outcome_names, weights=self._outcome_weights, k=1)[0]

    def _timestamp_for_tick(self) -> datetime:
        return _SCENARIO_EPOCH + timedelta(seconds=self.tick)

    def _build_payload(self, asset_id: str, outcome: Outcome) -> tuple[str, dict[str, Any], str]:
        state = self._states[asset_id]
        ts = self._timestamp_for_tick()

        if outcome in {"cv_low_confidence", "cv_high_confidence"}:
            kind = "camera_frame"
        elif outcome == "drift_signature":
            kind = "sensor_ping"
        elif outcome in {"sensor_corrupt", "contract_violation"}:
            kind = "sensor_ping" if self._rng.random() < 0.5 else "camera_frame"
        else:
            kind = "camera_frame" if self._rng.random() < 0.35 else "sensor_ping"

        if outcome == "sensor_corrupt":
            event_id = f"evt_{self.tick:08d}"
            if kind == "sensor_ping":
                payload = {
                    "event_type": "sensor_ping",
                    "asset_id": asset_id,
                    # missing device_id / timestamp — fails structural triage
                    "speed_mph": "not-a-number",
                    "synthetic_scenario": True,
                    "scenario_id": self.scenario_id,
                    "scenario_outcome": outcome,
                }
            else:
                payload = {
                    "event_type": "camera_frame",
                    "asset_id": asset_id,
                    "frame_id": "bad_frame",
                    "synthetic_scenario": True,
                    "scenario_id": self.scenario_id,
                    "scenario_outcome": outcome,
                }
            return kind, payload, event_id

        if outcome == "contract_violation":
            event_id = f"evt_{self.tick:08d}"
            if kind == "sensor_ping":
                payload = {
                    "schema_version": "1.0.0",
                    "event_type": "sensor_ping",
                    "asset_id": asset_id,
                    "device_id": state.device_id,
                    "timestamp": ts.isoformat().replace("+00:00", "Z"),
                    "speed_mph": 999.0,  # out of contract range
                    "latitude": 0.0,
                    "longitude": 0.0,
                    "heading_deg": 0.0,
                    "odometer_km": -5.0,
                    "synthetic_scenario": True,
                    "scenario_id": self.scenario_id,
                    "scenario_outcome": outcome,
                }
            else:
                payload = {
                    "schema_version": "1.0.0",
                    "event_type": "camera_frame",
                    "asset_id": asset_id,
                    "device_id": state.camera_device_id,
                    "frame_id": f"frm_{self._rng.randbytes(6).hex()}",
                    "timestamp": ts.isoformat().replace("+00:00", "Z"),
                    "storage_uri": "http://not-allowed.example/frame.jpg",
                    "content_type": "image/jpeg",
                    "width_px": 640,
                    "height_px": 480,
                    "synthetic_scenario": True,
                    "scenario_id": self.scenario_id,
                    "scenario_outcome": outcome,
                }
            return kind, payload, event_id

        # Valid payloads from here
        if kind == "sensor_ping":
            speed = state.speed_mph
            lat = state.latitude
            lon = state.longitude
            if outcome == "drift_signature":
                # Statistically shifted numerics for this asset (Phase 16 foreshadow).
                speed = min(120.0, speed + 40.0 + 10.0 * math.sin(self.tick))
                lat = min(90.0, lat + 0.5)
                lon = max(-180.0, lon - 0.5)
            ping = SensorPing(
                asset_id=asset_id,
                device_id=state.device_id,
                timestamp=ts,
                speed_mph=round(speed, 2),
                latitude=round(lat, 7),
                longitude=round(lon, 7),
                heading_deg=round(state.heading_deg % 360.0, 2),
                odometer_km=round(state.odometer_km + self.tick * 0.01, 2),
                fuel_level_pct=round(state.fuel_level_pct, 2),
                synthetic_scenario=True,
                scenario_id=self.scenario_id,
                scenario_outcome=outcome if outcome != "clean" else None,
            )
            payload = ping.to_payload()
            event_id = f"ping_{self.tick:08d}"
            return kind, payload, event_id

        frame_id = f"frm_{self._rng.randbytes(6).hex()}"
        day = ts.strftime("%Y-%m-%d")
        frame = CameraFrameMetadata(
            asset_id=asset_id,
            device_id=state.camera_device_id,
            frame_id=frame_id,
            timestamp=ts,
            storage_uri=(
                f"file://bronze/raw_frames/dt={day}/device={state.camera_device_id}/{frame_id}.jpg"
            ),
            width_px=1280,
            height_px=720,
            synthetic_scenario=True,
            scenario_id=self.scenario_id,
            scenario_outcome=outcome if outcome != "clean" else None,
        )
        return "camera_frame", frame.to_payload(), frame_id
