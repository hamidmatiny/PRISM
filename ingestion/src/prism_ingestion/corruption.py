"""Stable corruption-type taxonomy for rejected ingestion events.

Two independent gates classify rejections into the same enum so a DLQ reader
never has to care which gate fired:

* ``classify_structural_error`` — Layer 1 (Pydantic). Fast, cheap, catches
  missing/mistyped/out-of-declared-range/malformed-pattern fields. Prefers a
  live-simulator ``_corruption`` ground-truth hint when present (see
  ``simulator.py``); falls back to inspecting ``pydantic.ValidationError``
  locations/types for payloads with no hint (e.g. scenario-engine traffic).
* ``classify_contract_error`` — Layer 2 (Pandera). Structurally-valid but
  business-implausible records that Layer 1 cannot and should not police at
  the wire-format level (e.g. a (0, 0) "null island" GPS sentinel that is
  within Pydantic's -90..90 / -180..180 range but not a real fleet position).

Adapted from hydra-data-factory's two-pass pattern; enum values are PRISM's
own telemetry/CV-frame fields, not copied from hydra's AV-specific ones.
"""

from __future__ import annotations

from typing import Any, Literal

CorruptionType = Literal[
    "missing_required_field",
    "invalid_timestamp",
    "invalid_numeric_value",
    "malformed_identifier",
    "malformed_storage_uri",
    "malformed_geo",
    "scenario_field_inconsistent",
    "schema_validation",
    "bronze_contract_violation",
]

RejectionGate = Literal["structural", "contract"]

_NUMERIC_FIELDS = frozenset(
    {
        "speed_mph",
        "odometer_km",
        "heading_deg",
        "fuel_level_pct",
        "capture_exposure_ms",
        "width_px",
        "height_px",
    }
)
_IDENTIFIER_FIELDS = frozenset({"asset_id", "device_id", "frame_id"})
_GEO_FIELDS = frozenset({"latitude", "longitude"})
_SCENARIO_FIELDS = frozenset({"synthetic_scenario", "scenario_id", "scenario_outcome"})

# Ground-truth hints tagged by the live FleetSimulator's ``_corrupt_payload``
# (see simulator.py `strategies`). "malformed_uri" is ambiguous by itself —
# it means a bad storage_uri for camera_frame, but a bad latitude for
# sensor_ping (the live simulator has no URI field to corrupt on that kind) —
# so it is resolved together with ``kind`` below rather than as a flat map.
_HINT_MAP: dict[str, CorruptionType] = {
    "drop_asset_id": "missing_required_field",
    "null_timestamp": "invalid_timestamp",
    "invalid_speed_or_size": "invalid_numeric_value",
    "bad_id_pattern": "malformed_identifier",
}


def classify_structural_error(
    errors: list[dict[str, Any]],
    *,
    kind: str,
    hint: str | None = None,
) -> CorruptionType:
    """Classify a Layer-1 (Pydantic) rejection into a stable corruption_type.

    ``errors`` is the output of ``pydantic.ValidationError.errors()``.
    """
    if hint:
        if hint == "malformed_uri":
            return "malformed_storage_uri" if kind == "camera_frame" else "malformed_geo"
        mapped = _HINT_MAP.get(hint)
        if mapped is not None:
            return mapped

    for err in errors:
        loc = err.get("loc") or ()
        field = str(loc[0]) if loc else ""
        err_type = str(err.get("type") or "")

        if err_type == "missing":
            return "missing_required_field"
        if field == "timestamp":
            return "invalid_timestamp"
        if field in _NUMERIC_FIELDS:
            return "invalid_numeric_value"
        if field in _IDENTIFIER_FIELDS and err_type in {
            "string_pattern_mismatch",
            "string_too_short",
            "string_too_long",
        }:
            return "malformed_identifier"
        if field in _GEO_FIELDS:
            return "malformed_geo"
        if field == "storage_uri":
            return "malformed_storage_uri"
        if field in _SCENARIO_FIELDS:
            return "scenario_field_inconsistent"

    return "schema_validation"


def classify_contract_error(*, kind: str, checks_failed: tuple[str, ...]) -> CorruptionType:
    """Classify a Layer-2 (Pandera) rejection into a stable corruption_type.

    ``checks_failed`` holds the distinct Pandera ``Check.error`` messages that
    fired (Pandera's ``failure_cases`` table exposes the check's ``error``
    text under its ``check`` column for dataframe-wide checks, not the
    ``name=`` kwarg, so matching is done on message content).
    """
    for message in checks_failed:
        if "null-island" in message:
            return "malformed_geo"
        if "storage_uri must start" in message:
            return "malformed_storage_uri"
    return "bronze_contract_violation"
