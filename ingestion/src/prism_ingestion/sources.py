"""Event sources for ingestion — live simulator or scenario-engine pull."""

from __future__ import annotations

import logging
from typing import Any, Protocol

import httpx

from prism_ingestion.simulator import EventKind, FleetSimulator

logger = logging.getLogger(__name__)


class EventSource(Protocol):
    def generate_event(self) -> tuple[EventKind, dict[str, Any]] | None:
        """Return (kind, payload), or None when the tick should be skipped."""


class LiveEventSource:
    def __init__(self, simulator: FleetSimulator) -> None:
        self._simulator = simulator

    def generate_event(self) -> tuple[EventKind, dict[str, Any]] | None:
        return self._simulator.generate_event()


class ScenarioClient:
    """HTTP pull client for scenario-engine ``GET /v1/next-event``."""

    def __init__(self, base_url: str, *, timeout_s: float = 5.0) -> None:
        self._base = base_url.rstrip("/")
        self._timeout = timeout_s

    def generate_event(self) -> tuple[EventKind, dict[str, Any]] | None:
        url = f"{self._base}/v1/next-event"
        try:
            with httpx.Client(timeout=self._timeout) as client:
                resp = client.get(url)
                resp.raise_for_status()
                body = resp.json()
        except Exception as exc:  # noqa: BLE001 — surface as skip + log
            logger.warning("scenario-engine pull failed: %s", exc)
            return None

        if body.get("skip"):
            logger.debug(
                "scenario skip tick=%s asset=%s reason=%s",
                body.get("tick"),
                body.get("asset_id"),
                body.get("reason") or body.get("outcome"),
            )
            return None

        kind = body.get("kind")
        payload = body.get("payload")
        if kind not in {"sensor_ping", "camera_frame"} or not isinstance(payload, dict):
            logger.warning("scenario-engine returned invalid envelope: %s", body)
            return None
        return kind, payload  # type: ignore[return-value]
