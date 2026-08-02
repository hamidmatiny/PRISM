"""Contract gate — accept schema-valid events, reject the rest to DLQ."""

from __future__ import annotations

from typing import Any

from pydantic import ValidationError

from prism_ingestion.simulator import EventKind
from prism_telemetry_schema import CameraFrameMetadata, SensorPing


def validate_event(
    kind: EventKind,
    payload: dict[str, Any],
) -> tuple[bool, dict[str, Any], str | None]:
    """
    Validate ``payload`` against the telemetry contract for ``kind``.

    Returns ``(ok, cleaned_payload_or_original, error_message)``.
    """
    working = {k: v for k, v in payload.items() if not k.startswith("_")}
    try:
        if kind == "sensor_ping":
            model = SensorPing.model_validate(working)
        else:
            model = CameraFrameMetadata.model_validate(working)
        return True, model.to_payload(), None
    except ValidationError as exc:
        return False, payload, str(exc)
