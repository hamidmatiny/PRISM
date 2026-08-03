"""HTTP clients for drift-monitor + scenario-engine (fail-open friendly)."""

from __future__ import annotations

from typing import Any

import httpx


def get_drift_status(base_url: str, *, timeout_s: float = 10.0) -> dict[str, Any]:
    url = f"{base_url.rstrip('/')}/v1/status"
    with httpx.Client(timeout=timeout_s) as client:
        resp = client.get(url)
        resp.raise_for_status()
        return resp.json()


def assets_with_drift(status: dict[str, Any]) -> list[dict[str, Any]]:
    """Return assets that have a last_detection with drifted_feature_count >= 1."""
    found: list[dict[str, Any]] = []
    for asset_id, body in (status.get("assets") or {}).items():
        last = body.get("last_detection") or {}
        for group, det in last.items():
            count = int(det.get("drifted_feature_count") or 0)
            if count >= 1:
                found.append(
                    {
                        "asset_id": asset_id,
                        "group": group,
                        "drifted_feature_count": count,
                    }
                )
    return found


def reset_scenario(
    base_url: str,
    *,
    seed: int,
    scenario_id: str | None = None,
    weights: dict[str, float] | None = None,
    timeout_s: float = 10.0,
) -> dict[str, Any]:
    body: dict[str, Any] = {"seed": seed}
    if scenario_id:
        body["scenario_id"] = scenario_id
    if weights is not None:
        body["weights"] = weights
    url = f"{base_url.rstrip('/')}/v1/reset"
    with httpx.Client(timeout=timeout_s) as client:
        resp = client.post(url, json=body)
        resp.raise_for_status()
        return resp.json()


def pull_next_events(base_url: str, *, ticks: int, timeout_s: float = 10.0) -> list[dict[str, Any]]:
    url = f"{base_url.rstrip('/')}/v1/next-event"
    out: list[dict[str, Any]] = []
    with httpx.Client(timeout=timeout_s) as client:
        for _ in range(ticks):
            resp = client.get(url)
            resp.raise_for_status()
            out.append(resp.json())
    return out
