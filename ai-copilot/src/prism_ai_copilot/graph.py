"""Ask PRISM orchestration — tools first, then grounded template synthesis."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import httpx

from prism_ai_copilot.config import CopilotConfig
from prism_ai_copilot.non_fabrication import EvidenceItem, add_id
from prism_ai_copilot.synthesize import _asset_filter, select_tools, synthesize_answer
from prism_ai_copilot.tools.cv_findings import query_cv_findings
from prism_ai_copilot.tools.warehouse import query_warehouse
from prism_ai_copilot.tools.work_orders import query_work_orders
from prism_ai_copilot.validation import sanitize_answer, validate_question


@dataclass
class AskResult:
    answer: str
    grounded: bool
    tools_used: list[str]
    tool_calls: list[dict[str, Any]]
    evidence: list[dict[str, Any]]
    redactions: list[str]
    error: str | None = None


def run_ask(
    question: str,
    *,
    config: CopilotConfig,
    control_plane_token: str | None = None,
    client: httpx.Client | None = None,
) -> AskResult:
    check = validate_question(question)
    if not check.ok:
        return AskResult(
            answer="",
            grounded=False,
            tools_used=[],
            tool_calls=[],
            evidence=[],
            redactions=[],
            error=check.reason,
        )

    token = (control_plane_token or config.control_plane_token or "").strip()
    tools = select_tools(check.sanitized)
    evidence: list[EvidenceItem] = []
    # User-supplied asset ids are in-scope for this turn (not invented by the model).
    asked_asset = _asset_filter(check.sanitized)
    if asked_asset:
        add_id(evidence, "question", "asset_id", asked_asset)
    tool_calls: list[dict[str, Any]] = []
    warehouse: dict[str, Any] | None = None
    cv: dict[str, Any] | None = None
    work_orders: dict[str, Any] | None = None

    own = client is None
    http = client or httpx.Client()
    try:
        for name in tools:
            try:
                if name == "query_warehouse":
                    warehouse = query_warehouse(
                        base_url=config.activation_url,
                        evidence=evidence,
                        client=http,
                    )
                    tool_calls.append(
                        {
                            "tool": name,
                            "ok": True,
                            "row_count": warehouse["row_count"],
                            "warehouse": warehouse["warehouse"],
                        }
                    )
                elif name == "query_cv_findings":
                    cv = query_cv_findings(
                        control_plane_url=config.control_plane_url,
                        token=token,
                        gold_dir=config.cv_findings_gold_dir,
                        evidence=evidence,
                        client=http,
                    )
                    tool_calls.append(
                        {
                            "tool": name,
                            "ok": True,
                            "pending_count": cv["pending_count"],
                            "findings_count": cv["findings_count"],
                            "gold_count": cv["gold_count"],
                        }
                    )
                elif name == "query_work_orders":
                    work_orders = query_work_orders(
                        base_url=config.control_plane_url,
                        token=token,
                        evidence=evidence,
                        client=http,
                    )
                    tool_calls.append(
                        {
                            "tool": name,
                            "ok": True,
                            "count": work_orders["count"],
                            "open_count": work_orders["open_count"],
                        }
                    )
            except Exception as exc:  # noqa: BLE001 — surface tool failure honestly
                tool_calls.append({"tool": name, "ok": False, "error": str(exc)})
    finally:
        if own:
            http.close()

    if not any(c.get("ok") for c in tool_calls):
        return AskResult(
            answer=(
                "No tool calls succeeded in this turn, so I cannot make factual claims. "
                f"Failures: {tool_calls!r}"
            ),
            grounded=True,
            tools_used=tools,
            tool_calls=tool_calls,
            evidence=[e.to_dict() for e in evidence],
            redactions=[],
            error="all_tools_failed",
        )

    try:
        answer = synthesize_answer(
            check.sanitized,
            warehouse=warehouse,
            cv=cv,
            work_orders=work_orders,
            evidence=evidence,
        )
    except AssertionError as exc:
        return AskResult(
            answer=(
                "I refuse to answer because a draft claim was not grounded in this turn's "
                f"tool evidence ({exc})."
            ),
            grounded=False,
            tools_used=tools,
            tool_calls=tool_calls,
            evidence=[e.to_dict() for e in evidence],
            redactions=[],
            error="non_fabrication",
        )

    answer, redactions = sanitize_answer(answer)
    return AskResult(
        answer=answer,
        grounded=True,
        tools_used=tools,
        tool_calls=tool_calls,
        evidence=[e.to_dict() for e in evidence],
        redactions=redactions,
    )
