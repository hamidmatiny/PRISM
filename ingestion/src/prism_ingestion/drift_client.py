"""Best-effort feature reporting to drift-monitor (Phase 16).

Same fire-and-forget, fail-open pattern as incident_client.py --
drift-monitor being unreachable never blocks or slows ingestion.
"""

from __future__ import annotations

import logging
from typing import Any

import httpx

logger = logging.getLogger(__name__)

_client: httpx.Client | None = None


def _get_client(timeout_s: float) -> httpx.Client:
    global _client
    if _client is None:
        _client = httpx.Client(timeout=timeout_s, trust_env=False)
    return _client


def report_telemetry_features(
    drift_monitor_url: str,
    *,
    asset_id: str | None,
    payload: dict[str, Any],
    synthetic_scenario: bool,
    timeout_s: float = 1.0,
) -> None:
    if not drift_monitor_url or not asset_id:
        return
    url = f"{drift_monitor_url.rstrip('/')}/v1/observe"
    body: dict[str, Any] = {
        "asset_id": asset_id,
        "group": "telemetry_numeric",
        "payload": payload,
        "synthetic_scenario": synthetic_scenario,
    }
    try:
        _get_client(timeout_s).post(url, json=body)
    except Exception as exc:  # noqa: BLE001 — best-effort, never break the pipeline
        logger.debug("drift-monitor feature report failed (non-fatal): %s", exc)
