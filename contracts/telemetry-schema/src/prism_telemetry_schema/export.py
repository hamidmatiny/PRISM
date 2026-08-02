"""Export Pydantic models to committed JSON Schema documents."""

from __future__ import annotations

import json
from pathlib import Path

from prism_telemetry_schema.models import CameraFrameMetadata, SensorPing

_SCHEMA_DIR = Path(__file__).resolve().parents[2] / "schemas"


def schema_dir() -> Path:
    return _SCHEMA_DIR


def export_json_schemas(*, write: bool = True) -> dict[str, dict]:
    """Return (and optionally write) JSON Schema docs for telemetry models."""
    schemas = {
        "sensor_ping.schema.json": SensorPing.model_json_schema(),
        "camera_frame_metadata.schema.json": CameraFrameMetadata.model_json_schema(),
    }
    if write:
        _SCHEMA_DIR.mkdir(parents=True, exist_ok=True)
        for name, schema in schemas.items():
            path = _SCHEMA_DIR / name
            path.write_text(json.dumps(schema, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return schemas


if __name__ == "__main__":
    written = export_json_schemas(write=True)
    for name in written:
        print(f"wrote {_SCHEMA_DIR / name}")
