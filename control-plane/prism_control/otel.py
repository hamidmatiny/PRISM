"""OpenTelemetry bootstrap for Django (no-op without OTLP endpoint)."""

from __future__ import annotations

_instrumented = False


def setup() -> bool:
    global _instrumented
    if _instrumented:
        return True
    try:
        from prism_otel import instrument_django
    except ImportError:
        return False
    active = instrument_django("control-plane")
    _instrumented = active
    return active
