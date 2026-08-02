"""Tool: query control-plane work orders."""

from __future__ import annotations

from typing import Any

import httpx

from prism_ai_copilot.non_fabrication import EvidenceItem, add_id, add_number

TOOL_NAME = "query_work_orders"


def query_work_orders(
    *,
    base_url: str,
    token: str,
    evidence: list[EvidenceItem],
    asset_id: str | None = None,
    client: httpx.Client | None = None,
) -> dict[str, Any]:
    if not token:
        raise ValueError("control-plane token required for query_work_orders")

    params = {"asset_id": asset_id} if asset_id else None
    own = client is None
    client = client or httpx.Client()
    try:
        res = client.get(
            f"{base_url}/api/v1/work-orders",
            params=params,
            headers={"Authorization": f"Bearer {token}"},
            timeout=30.0,
        )
        res.raise_for_status()
        orders = res.json()
    finally:
        if own:
            client.close()

    if not isinstance(orders, list):
        raise ValueError("work-orders response is not a list")

    open_statuses = {"open", "in_progress"}
    open_count = sum(1 for o in orders if str(o.get("status", "")).lower() in open_statuses)
    add_number(evidence, TOOL_NAME, "work_order_count", len(orders))
    add_number(evidence, TOOL_NAME, "open_work_order_count", open_count)

    for i, o in enumerate(orders):
        if o.get("work_order_id"):
            add_id(evidence, TOOL_NAME, f"work_order_id:{i}", str(o["work_order_id"]))
        if o.get("asset_id"):
            add_id(evidence, TOOL_NAME, f"asset_id:{i}", str(o["asset_id"]))
        if o.get("status"):
            add_id(evidence, TOOL_NAME, f"status:{i}", str(o["status"]))

    return {
        "tool": TOOL_NAME,
        "orders": orders,
        "count": len(orders),
        "open_count": open_count,
    }
