"""Layer 2 — Pandera contract gate.

Pydantic (Layer 1, ``validate.py``) enforces the wire-format request shape:
types, required fields, and per-field declared ranges. This layer re-asserts
a smaller, independent set of checks against the *storage/analytics contract*
the bronze zone and downstream lakehouse actually rely on, using a different
technology (tabular, dtype-first) so a bug or gap in the Pydantic model isn't
the only thing standing between bad data and bronze.

The concrete, verified gap this closes: a sensor ping with
latitude == longitude == 0.0 ("null island") passes Pydantic today because
0.0 is a legal value inside the declared -90..90 / -180..180 ranges — but it
is never a real PRISM fleet position. See docs/phases/PHASE_13_COMPLETION.md
for the before/after proof.
"""

from __future__ import annotations

from typing import Any

import pandera.errors
import pandera.pandas as pa

SENSOR_PING_SCHEMA = pa.DataFrameSchema(
    {
        "asset_id": pa.Column(str, nullable=False),
        "device_id": pa.Column(str, nullable=False),
        "speed_mph": pa.Column(float, pa.Check.in_range(0.0, 120.0), nullable=False),
        "latitude": pa.Column(float, pa.Check.in_range(-90.0, 90.0), nullable=False),
        "longitude": pa.Column(float, pa.Check.in_range(-180.0, 180.0), nullable=False),
        "odometer_km": pa.Column(float, pa.Check.ge(0.0), nullable=False),
    },
    checks=[
        pa.Check(
            lambda df: ~((df["latitude"] == 0.0) & (df["longitude"] == 0.0)),
            name="null_island_geo",
            error=(
                "latitude/longitude both exactly 0.0 "
                "(null-island sentinel, not a real fleet position)"
            ),
        ),
    ],
    strict=False,
    coerce=True,
)

CAMERA_FRAME_SCHEMA = pa.DataFrameSchema(
    {
        "asset_id": pa.Column(str, nullable=False),
        "device_id": pa.Column(str, nullable=False),
        "frame_id": pa.Column(str, nullable=False),
        "width_px": pa.Column(int, pa.Check.in_range(1, 16384), nullable=False),
        "height_px": pa.Column(int, pa.Check.in_range(1, 16384), nullable=False),
    },
    checks=[
        pa.Check(
            lambda df: df["storage_uri"].str.startswith(("s3://", "file://")),
            name="storage_uri_scheme",
            error="storage_uri must start with s3:// or file://",
        ),
    ],
    strict=False,
    coerce=True,
)

_SCHEMAS = {"sensor_ping": SENSOR_PING_SCHEMA, "camera_frame": CAMERA_FRAME_SCHEMA}


def check_contract(kind: str, cleaned: dict[str, Any]) -> tuple[bool, tuple[str, ...], str | None]:
    """Validate a Pydantic-cleaned record against the Layer-2 bronze contract.

    Returns ``(ok, failed_check_names, reason)``.
    """
    schema = _SCHEMAS.get(kind)
    if schema is None:
        return True, (), None

    import pandas as pd

    frame = pd.DataFrame([cleaned])
    try:
        schema.validate(frame, lazy=True)
    except pandera.errors.SchemaErrors as exc:
        failure_cases = exc.failure_cases
        check_names = tuple(sorted(set(failure_cases["check"].dropna().astype(str).tolist())))
        reason = "; ".join(
            f"{row.get('column', 'dataframe')}: {row.get('check')}"
            for _, row in failure_cases.iterrows()
        )
        return False, check_names, reason or str(exc)
    return True, (), None
