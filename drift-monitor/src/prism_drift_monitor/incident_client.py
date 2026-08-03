"""Best-effort drift-observation reporting to incident-engine (Phase 16).

Exact fire-and-forget, fail-open pattern as ingestion's and cv-service's
incident_client.py -- incident-engine being unreachable never blocks
detection; a failed report just means that one detection result never
became a breaker observation.
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


def report_drift(
    incident_engine_url: str,
    *,
    asset_id: str,
    drifted_feature_count: int,
    detail: dict[str, Any],
    timeout_s: float = 1.0,
) -> None:
    if not incident_engine_url or not asset_id:
        return
    url = f"{incident_engine_url.rstrip('/')}/v1/observations"
    body: dict[str, Any] = {
        "asset_id": asset_id,
        "kind": "drift",
        "detail": {"drifted_feature_count": drifted_feature_count, **detail},
    }
    try:
        _get_client(timeout_s).post(url, json=body)
    except Exception as exc:  # noqa: BLE001 — best-effort, never break detection
        logger.debug("incident-engine drift observation report failed (non-fatal): %s", exc)
