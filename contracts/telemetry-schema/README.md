# telemetry-schema

Pydantic + JSON Schema contracts for fleet telemetry.

| Model | JSON Schema | Purpose |
|-------|-------------|---------|
| `SensorPing` | `schemas/sensor_ping.schema.json` | Sensor observation (speed, GPS, fuel, …) |
| `CameraFrameMetadata` | `schemas/camera_frame_metadata.schema.json` | Frame metadata + storage URI |

## Field discipline

Same bar as hydra-data-factory `schema_contract.py`:

- Regex IDs: `PRISM-AST-\d{3}`, `PRISM-DEV-\d{3}`, `frm_[0-9a-f]{12}`
- Typed ranges: speed 0–120 mph, lat/lon WGS-84, heading 0–360
- Required timezone-aware UTC timestamps (naive rejected)

## Install / use

```bash
pip install -e contracts/telemetry-schema
python -c "from prism_telemetry_schema import SensorPing; print(SensorPing)"
python -m prism_telemetry_schema.export   # regenerate schemas/
```

**Health / port:** N/A (library package).
