"""Template synthesis — no paid LLM; answers filled only from tool evidence (ADR-004)."""

from __future__ import annotations

import re
from typing import Any

from prism_ai_copilot.non_fabrication import (
    EvidenceItem,
    add_number,
    assert_answer_grounded,
    format_number,
)


def _wants_warehouse(q: str) -> bool:
    return bool(
        re.search(
            r"\b(ping|telemetry|warehouse|redshift|snowflake|asset_daily|metrics?|sensor)\b",
            q,
            re.I,
        )
    )


def _wants_cv(q: str) -> bool:
    return bool(
        re.search(
            r"\b(cv|finding|defect|review|queue|anomaly|dent|crack|tire|camera)\b",
            q,
            re.I,
        )
    )


def _wants_work_orders(q: str) -> bool:
    return bool(re.search(r"\b(work[\s-]?order|wo\b|maintenance|ticket)\b", q, re.I))


def select_tools(question: str) -> list[str]:
    """Keyword router — explicit, testable, no LLM."""
    q = question.lower()
    tools: list[str] = []
    if _wants_warehouse(q):
        tools.append("query_warehouse")
    if _wants_cv(q):
        tools.append("query_cv_findings")
    if _wants_work_orders(q):
        tools.append("query_work_orders")
    # Broad fleet questions → all three tools.
    if not tools or re.search(r"\b(fleet|overview|status|summary|how many)\b", q, re.I):
        tools = ["query_warehouse", "query_cv_findings", "query_work_orders"]
    # de-dupe preserve order
    seen: set[str] = set()
    out: list[str] = []
    for t in tools:
        if t not in seen:
            seen.add(t)
            out.append(t)
    return out


def _asset_filter(question: str) -> str | None:
    m = re.search(r"\b(PRISM-AST-\d+)\b", question, re.I)
    if not m:
        return None
    # Canonical form matches activation-gateway / control-plane ids.
    return m.group(1).upper()


def synthesize_answer(
    question: str,
    *,
    warehouse: dict[str, Any] | None,
    cv: dict[str, Any] | None,
    work_orders: dict[str, Any] | None,
    evidence: list[EvidenceItem],
) -> str:
    """Build a grounded answer. Ungrounded claims are refused, not invented."""
    asset = _asset_filter(question)
    parts: list[str] = []

    if warehouse is not None:
        rows = warehouse.get("rows") or []
        wh = warehouse.get("warehouse", "unknown")
        table = warehouse.get("table", "asset_daily_metrics")
        if asset:
            match = next((r for r in rows if str(r.get("asset_id", "")).upper() == asset), None)
            if match and "ping_count" in match:
                parts.append(
                    f"From {wh} table {table}: {asset} ping_count="
                    f"{format_number(match['ping_count'])}."
                )
            else:
                parts.append(
                    f"I queried {wh}/{table} but found no telemetry row for {asset} "
                    f"in this turn's tool results — I will not invent a ping_count."
                )
        else:
            if rows:
                bits = [
                    f"{r.get('asset_id')} ping_count={format_number(r['ping_count'])}"
                    for r in rows
                    if "ping_count" in r and r.get("asset_id")
                ]
                parts.append(
                    f"Warehouse {wh} ({table}) returned {format_number(len(rows))} row(s): "
                    + "; ".join(bits)
                    + "."
                )
            else:
                parts.append(
                    f"Warehouse query on {table} via {wh} returned 0 rows in this turn — "
                    "no telemetry figures to report."
                )

    if cv is not None:
        pending_n = int(cv.get("pending_count", 0))
        findings_n = int(cv.get("findings_count", 0))
        gold_n = int(cv.get("gold_count", 0))
        pending = cv.get("pending") or []
        if asset:
            asset_pending = [p for p in pending if str(p.get("asset_id", "")).upper() == asset]
            # Counts derived from this turn's tool payload must be evidence too (ADR-004).
            add_number(
                evidence,
                "synthesize",
                f"cv:{asset}:pending",
                float(len(asset_pending)),
            )
            parts.append(
                f"CV store: {asset} has {format_number(len(asset_pending))} unreviewed "
                f"queue finding(s) (fleet pending_count={format_number(pending_n)}, "
                f"findings_count={format_number(findings_n)}, "
                f"gold_count={format_number(gold_n)})."
            )
            if asset_pending:
                top = asset_pending[0]
                parts.append(
                    f"Top queue item for {asset}: {top.get('finding_id')} "
                    f"defect_class={top.get('defect_class')} "
                    f"confidence={format_number(float(top.get('confidence', 0)))}."
                )
        else:
            parts.append(
                f"CV-finding store: pending_count={format_number(pending_n)}, "
                f"findings_count={format_number(findings_n)}, "
                f"gold_count={format_number(gold_n)}."
            )
            if pending:
                sample = pending[0]
                parts.append(
                    f"Example queue finding {sample.get('finding_id')} on "
                    f"{sample.get('asset_id')} "
                    f"defect_class={sample.get('defect_class')} "
                    f"confidence={format_number(float(sample.get('confidence', 0)))}."
                )

    if work_orders is not None:
        total = int(work_orders.get("count", 0))
        open_n = int(work_orders.get("open_count", 0))
        orders = work_orders.get("orders") or []
        if asset:
            asset_orders = [o for o in orders if str(o.get("asset_id", "")).upper() == asset]
            add_number(
                evidence,
                "synthesize",
                f"wo:{asset}:count",
                float(len(asset_orders)),
            )
            parts.append(
                f"Control-plane work orders for {asset}: "
                f"{format_number(len(asset_orders))} "
                f"(fleet total={format_number(total)}, open={format_number(open_n)})."
            )
        else:
            parts.append(
                f"Control-plane work orders: total={format_number(total)}, "
                f"open_count={format_number(open_n)}."
            )
            if orders:
                o0 = orders[0]
                parts.append(
                    f"Example work order {o0.get('work_order_id')} on {o0.get('asset_id')} "
                    f"status={o0.get('status')}."
                )

    if not parts:
        answer = (
            "I could not ground an answer in tool results for this question. "
            "Ask about telemetry/ping_count, CV findings, or work orders."
        )
    else:
        answer = " ".join(parts)

    # Structural non-fabrication gate before returning.
    assert_answer_grounded(answer, evidence)
    return answer
