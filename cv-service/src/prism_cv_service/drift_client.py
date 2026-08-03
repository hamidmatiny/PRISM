"""Best-effort CV feature reporting to drift-monitor (Phase 16).

Same fire-and-forget, fail-open pattern as incident_client.py.
CvFinding has no synthetic_scenario field -- every detection this service
runs is a genuine ONNX inference over real image bytes, regardless of
whether the frame's originating metadata came from the live simulator or
scenario-engine, so this always reports synthetic_scenario=False.
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


def report_cv_finding_features(
    drift_monitor_url: str,
    *,
    asset_id: str | None,
    finding_payload: dict[str, Any],
    timeout_s: float = 1.0,
) -> None:
    if not drift_monitor_url or not asset_id:
        return
    url = f"{drift_monitor_url.rstrip('/')}/v1/observe"
    body: dict[str, Any] = {
        "asset_id": asset_id,
        "group": "cv_geometry",
        "payload": finding_payload,
        "synthetic_scenario": False,
    }
    try:
        _get_client(timeout_s).post(url, json=body)
    except Exception as exc:  # noqa: BLE001 — best-effort, never break detection
        logger.debug("drift-monitor feature report failed (non-fatal): %s", exc)
