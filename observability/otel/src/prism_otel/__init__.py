"""PRISM OpenTelemetry helpers."""

from __future__ import annotations

from prism_otel.setup import (
    get_tracer,
    instrument_django,
    instrument_fastapi,
    instrument_httpx,
    setup_tracing,
)

__all__ = [
    "get_tracer",
    "instrument_django",
    "instrument_fastapi",
    "instrument_httpx",
    "setup_tracing",
]
