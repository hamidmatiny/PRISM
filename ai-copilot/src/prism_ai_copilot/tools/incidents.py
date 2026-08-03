"""Tools: query incident-engine (Phase 14/15) — breakers and incidents.

Same ADR-004 non-fabrication contract as every other Ask PRISM tool: every
number or id the answer text mentions must be added as evidence here, from
the real HTTP response, or the answer gets refused before it's ever returned.
"""

from __future__ import annotations

from typing import Any

import httpx

from prism_ai_copilot.non_fabrication import EvidenceItem, add_id, add_number

QUERY_BREAKERS_TOOL_NAME = "query_breakers"
QUERY_INCIDENTS_TOOL_NAME = "query_incidents"


def query_breakers(
    *,
    incident_engine_url: str,
    evidence: list[EvidenceItem],
    asset_id: str | None = None,
    client: httpx.Client | None = None,
) -> dict[str, Any]:
    own = client is None
    client = client or httpx.Client()
    try:
        if asset_id:
            res = client.get(f"{incident_engine_url}/breakers/{asset_id}", timeout=10.0)
            res.raise_for_status()
            breakers = [res.json()]
        else:
            res = client.get(f"{incident_engine_url}/breakers", timeout=10.0)
            res.raise_for_status()
            breakers = res.json().get("breakers", [])
    finally:
        if own:
            client.close()

    if not isinstance(breakers, list):
        raise ValueError("breakers response is not a list")

    open_count = sum(1 for b in breakers if b.get("state") == "open")
    half_open_count = sum(1 for b in breakers if b.get("state") == "half_open")
    closed_count = sum(1 for b in breakers if b.get("state") == "closed")

    add_number(evidence, QUERY_BREAKERS_TOOL_NAME, "breaker_count", len(breakers))
    add_number(evidence, QUERY_BREAKERS_TOOL_NAME, "open_breaker_count", open_count)
    add_number(evidence, QUERY_BREAKERS_TOOL_NAME, "half_open_breaker_count", half_open_count)
    add_number(evidence, QUERY_BREAKERS_TOOL_NAME, "closed_breaker_count", closed_count)
    for i, b in enumerate(breakers):
        if b.get("asset_id"):
            add_id(evidence, QUERY_BREAKERS_TOOL_NAME, f"asset_id:{i}", str(b["asset_id"]))
        if b.get("state"):
            add_id(evidence, QUERY_BREAKERS_TOOL_NAME, f"state:{i}", str(b["state"]))
        if b.get("trip_reason"):
            add_id(evidence, QUERY_BREAKERS_TOOL_NAME, f"trip_reason:{i}", str(b["trip_reason"]))
        if b.get("incident_id"):
            add_id(evidence, QUERY_BREAKERS_TOOL_NAME, f"incident_id:{i}", str(b["incident_id"]))

    return {
        "tool": QUERY_BREAKERS_TOOL_NAME,
        "breakers": breakers,
        "count": len(breakers),
        "open_count": open_count,
        "half_open_count": half_open_count,
        "closed_count": closed_count,
    }


def query_incidents(
    *,
    incident_engine_url: str,
    evidence: list[EvidenceItem],
    status: str | None = None,
    client: httpx.Client | None = None,
) -> dict[str, Any]:
    if status is not None and status not in {"open", "acknowledged", "resolved"}:
        raise ValueError(f"status must be open|acknowledged|resolved, got {status!r}")

    params = {"status": status} if status else None
    own = client is None
    client = client or httpx.Client()
    try:
        res = client.get(f"{incident_engine_url}/incidents", params=params, timeout=10.0)
        res.raise_for_status()
        body = res.json()
    finally:
        if own:
            client.close()

    incidents = body.get("incidents", [])
    if not isinstance(incidents, list):
        raise ValueError("incidents response is not a list")

    add_number(evidence, QUERY_INCIDENTS_TOOL_NAME, "incident_count", len(incidents))
    for i, inc in enumerate(incidents):
        if inc.get("incident_id"):
            add_id(evidence, QUERY_INCIDENTS_TOOL_NAME, f"incident_id:{i}", str(inc["incident_id"]))
        if inc.get("asset_id"):
            add_id(evidence, QUERY_INCIDENTS_TOOL_NAME, f"asset_id:{i}", str(inc["asset_id"]))
        if inc.get("status"):
            add_id(evidence, QUERY_INCIDENTS_TOOL_NAME, f"status:{i}", str(inc["status"]))
        if inc.get("trigger"):
            add_id(evidence, QUERY_INCIDENTS_TOOL_NAME, f"trigger:{i}", str(inc["trigger"]))
        if inc.get("trip_count") is not None:
            add_number(evidence, QUERY_INCIDENTS_TOOL_NAME, f"trip_count:{i}", inc["trip_count"])

    return {
        "tool": QUERY_INCIDENTS_TOOL_NAME,
        "incidents": incidents,
        "count": len(incidents),
    }
