"""Tool: query the CV-finding store (control-plane APIs + gold writeback dir)."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import httpx

from prism_ai_copilot.non_fabrication import EvidenceItem, add_id, add_number, add_string

TOOL_NAME = "query_cv_findings"


def _ingest_finding(evidence: list[EvidenceItem], prefix: str, finding: dict[str, Any]) -> None:
    if finding.get("finding_id"):
        add_id(evidence, TOOL_NAME, f"{prefix}:finding_id", str(finding["finding_id"]))
    if finding.get("asset_id"):
        add_id(evidence, TOOL_NAME, f"{prefix}:asset_id", str(finding["asset_id"]))
    if finding.get("defect_class"):
        add_id(evidence, TOOL_NAME, f"{prefix}:defect_class", str(finding["defect_class"]))
    if finding.get("confidence") is not None:
        add_number(
            evidence,
            TOOL_NAME,
            f"{prefix}:confidence",
            float(finding["confidence"]),
        )
    if finding.get("queue_status"):
        add_string(evidence, TOOL_NAME, f"{prefix}:queue_status", str(finding["queue_status"]))


def _read_gold_dir(gold_dir: Path) -> list[dict[str, Any]]:
    if not gold_dir.is_dir():
        return []
    out: list[dict[str, Any]] = []
    for path in sorted(gold_dir.glob("*.json")):
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        if isinstance(payload, dict) and payload.get("finding_id"):
            out.append(payload)
    return out


def query_cv_findings(
    *,
    control_plane_url: str,
    token: str,
    gold_dir: Path,
    evidence: list[EvidenceItem],
    client: httpx.Client | None = None,
) -> dict[str, Any]:
    if not token:
        raise ValueError("control-plane token required for query_cv_findings")

    own = client is None
    client = client or httpx.Client()
    pending: list[dict[str, Any]] = []
    findings: list[dict[str, Any]] = []
    try:
        q = client.get(
            f"{control_plane_url}/api/v1/review-queue",
            headers={"Authorization": f"Bearer {token}"},
            timeout=30.0,
        )
        q.raise_for_status()
        pending = q.json()
        f = client.get(
            f"{control_plane_url}/api/v1/findings",
            headers={"Authorization": f"Bearer {token}"},
            timeout=30.0,
        )
        # findings list may be empty early; 200 required
        f.raise_for_status()
        findings = f.json()
    finally:
        if own:
            client.close()

    if not isinstance(pending, list):
        raise ValueError("review-queue response is not a list")
    if not isinstance(findings, list):
        raise ValueError("findings response is not a list")

    gold = _read_gold_dir(gold_dir)

    add_number(evidence, TOOL_NAME, "pending_count", len(pending))
    add_number(evidence, TOOL_NAME, "findings_count", len(findings))
    add_number(evidence, TOOL_NAME, "gold_count", len(gold))

    for i, item in enumerate(pending):
        _ingest_finding(evidence, f"pending:{i}", item)
    for i, item in enumerate(findings):
        _ingest_finding(evidence, f"finding:{i}", item)
    for i, item in enumerate(gold):
        _ingest_finding(evidence, f"gold:{i}", item)

    return {
        "tool": TOOL_NAME,
        "pending": pending,
        "findings": findings,
        "gold": gold,
        "pending_count": len(pending),
        "findings_count": len(findings),
        "gold_count": len(gold),
    }
