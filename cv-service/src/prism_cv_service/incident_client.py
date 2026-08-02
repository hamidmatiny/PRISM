"""Best-effort incident-engine client for cv-service (Phase 14).

Two directions:
* before deciding publish-vs-review, check whether the asset's breaker is
  open -- if so, force review regardless of confidence (the direct answer
  to "pause the source, not the whole pipeline": the asset stays degraded
  in the cockpit and every finding gets a human look until it recovers).
* after deciding, report qa_pass/qa_fail per finding so incident-engine's
  consecutive-QA-failure policy has real data to evaluate. A published
  (high-confidence) finding is qa_pass; a review-routed one is qa_fail --
  PRISM's confidence gate *is* its QA gate, there's no separate QA-validator
  stage to mirror Argus/sentinel-ray's more literally (documented adaptation,
  not a verbatim copy).

incident-engine being unreachable never blocks detection: breaker checks
fail open (treated as closed/normal), and observation reports are fire-and-
forget.
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


def breaker_is_open(incident_engine_url: str, asset_id: str, *, timeout_s: float = 1.0) -> bool:
    if not incident_engine_url:
        return False
    url = f"{incident_engine_url.rstrip('/')}/breakers/{asset_id}"
    try:
        resp = _get_client(timeout_s).get(url)
        if resp.status_code != 200:
            return False
        return resp.json().get("state") == "open"
    except Exception as exc:  # noqa: BLE001 — fail open, never block detection
        logger.debug("incident-engine breaker check failed (treating as closed): %s", exc)
        return False


def report_qa_observation(
    incident_engine_url: str,
    *,
    asset_id: str,
    passed: bool,
    timeout_s: float = 1.0,
) -> None:
    if not incident_engine_url or not asset_id:
        return
    url = f"{incident_engine_url.rstrip('/')}/v1/observations"
    body: dict[str, Any] = {"asset_id": asset_id, "kind": "qa_pass" if passed else "qa_fail"}
    try:
        _get_client(timeout_s).post(url, json=body)
    except Exception as exc:  # noqa: BLE001 — best-effort, never break the pipeline
        logger.debug("incident-engine qa observation report failed (non-fatal): %s", exc)
