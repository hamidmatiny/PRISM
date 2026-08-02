"""OpenTelemetry bootstrap — no-op unless OTLP endpoint is configured."""

from __future__ import annotations

import os
from typing import Any


def _enabled() -> bool:
    if os.environ.get("OTEL_SDK_DISABLED", "").lower() in {"1", "true", "yes"}:
        return False
    return bool(os.environ.get("OTEL_EXPORTER_OTLP_ENDPOINT", "").strip())


def setup_tracing(service_name: str) -> bool:
    """Configure tracer provider + OTLP HTTP exporter. Returns True if active."""
    if not _enabled():
        return False

    from opentelemetry import trace
    from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
    from opentelemetry.sdk.resources import Resource
    from opentelemetry.sdk.trace import TracerProvider
    from opentelemetry.sdk.trace.export import BatchSpanProcessor

    endpoint = os.environ["OTEL_EXPORTER_OTLP_ENDPOINT"].rstrip("/")
    # Prefer explicit traces path; collector accepts either.
    traces_ep = endpoint if endpoint.endswith("/v1/traces") else f"{endpoint}/v1/traces"

    resource = Resource.create(
        {
            "service.name": service_name,
            "service.namespace": "prism",
        }
    )
    provider = TracerProvider(resource=resource)
    provider.add_span_processor(BatchSpanProcessor(OTLPSpanExporter(endpoint=traces_ep)))
    trace.set_tracer_provider(provider)

    try:
        from opentelemetry.instrumentation.logging import LoggingInstrumentor

        LoggingInstrumentor().instrument(set_logging_format=True)
    except Exception:  # noqa: BLE001
        pass

    os.environ.setdefault("OTEL_SERVICE_NAME", service_name)
    return True


def instrument_fastapi(app: Any, service_name: str) -> bool:
    active = setup_tracing(service_name)
    if not active:
        return False
    from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor

    FastAPIInstrumentor.instrument_app(app)
    instrument_httpx()
    return True


def instrument_django(service_name: str) -> bool:
    active = setup_tracing(service_name)
    if not active:
        return False
    from opentelemetry.instrumentation.django import DjangoInstrumentor

    DjangoInstrumentor().instrument()
    instrument_httpx()
    return True


def instrument_httpx() -> None:
    if not _enabled():
        return
    try:
        import httpx  # noqa: F401
    except ImportError:
        pass
    else:
        try:
            from opentelemetry.instrumentation.httpx import HTTPXClientInstrumentor

            HTTPXClientInstrumentor().instrument()
        except Exception:  # noqa: BLE001
            pass
    try:
        import requests  # noqa: F401
    except ImportError:
        pass
    else:
        try:
            from opentelemetry.instrumentation.requests import RequestsInstrumentor

            RequestsInstrumentor().instrument()
        except Exception:  # noqa: BLE001
            pass


def get_tracer(name: str = "prism"):
    from opentelemetry import trace

    return trace.get_tracer(name)
