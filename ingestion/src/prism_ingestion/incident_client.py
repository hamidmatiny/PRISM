"""Best-effort observation reporting to incident-engine (Phase 14).

incident-engine being unreachable must never break ingestion -- same
graceful-degradation posture as scenario-engine pulls in sources.py. A
failed report just means breaker state doesn't update for that one event;
ingestion keeps landing bronze/DLQ exactly as it always has.

Uses one reused, ``trust_env=False`` client (never a proxied call -- this is
always a local sidecar) instead of building a fresh client per observation;
constructing an ``httpx.Client`` reads proxy environment variables every
time, which is real, measurable overhead at ingestion's event rate.
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


def report_observation(
    incident_engine_url: str,
    *,
    asset_id: str | None,
    kind: str,
    timeout_s: float = 1.0,
) -> None:
    if not incident_engine_url or not asset_id:
        return
    url = f"{incident_engine_url.rstrip('/')}/v1/observations"
    body: dict[str, Any] = {"asset_id": asset_id, "kind": kind}
    try:
        _get_client(timeout_s).post(url, json=body)
    except Exception as exc:  # noqa: BLE001 — best-effort, never break the pipeline
        logger.debug("incident-engine observation report failed (non-fatal): %s", exc)
