"""Tool: query activation-gateway (live warehouse via activation contract)."""

from __future__ import annotations

from typing import Any

import httpx

from prism_ai_copilot.non_fabrication import EvidenceItem, add_id, add_number

TOOL_NAME = "query_warehouse"
DEFAULT_TABLE = "asset_daily_metrics"
DEFAULT_SQL = (
    "SELECT asset_id, ping_count FROM asset_daily_metrics ORDER BY asset_id"
)


def ensure_activated(client: httpx.Client, base_url: str, table: str = DEFAULT_TABLE) -> None:
    """Idempotent activate — same contract shape cockpit uses."""
    import os
    from pathlib import Path

    candidates = [
        f"file:///data/lakehouse/gold/{table}",
        f"file:///app/activation-gateway/fixtures/gold/{table}",
    ]
    fixture_root = os.environ.get("PRISM_ACTIVATION_FIXTURE_GOLD")
    if fixture_root:
        candidates.append((Path(fixture_root) / table).resolve().as_uri())
    # Host checkout path (local `python -m prism_ai_copilot` outside compose).
    repo_root = Path(__file__).resolve().parents[4]
    host_fixture = repo_root / "activation-gateway" / "fixtures" / "gold" / table
    if host_fixture.is_dir():
        candidates.append(host_fixture.resolve().as_uri())

    for gold_uri in candidates:
        res = client.post(
            f"{base_url}/v1/activate",
            json={
                "gold_table": table,
                "warehouse": "redshift",
                "gold_uri": gold_uri,
                "set_primary": True,
            },
            timeout=30.0,
        )
        if res.status_code in {200, 409}:
            return
    # Last resort: let query fail with a clear error (table may already be activated).


def query_warehouse(
    *,
    base_url: str,
    evidence: list[EvidenceItem],
    sql: str = DEFAULT_SQL,
    table: str = DEFAULT_TABLE,
    client: httpx.Client | None = None,
) -> dict[str, Any]:
    own = client is None
    client = client or httpx.Client()
    try:
        ensure_activated(client, base_url, table)
        res = client.post(
            f"{base_url}/v1/query",
            json={"table": table, "warehouse": "auto", "sql": sql},
            timeout=30.0,
        )
        res.raise_for_status()
        payload = res.json()
    finally:
        if own:
            client.close()

    warehouse = str(payload.get("warehouse", "unknown"))
    add_id(evidence, TOOL_NAME, "warehouse", warehouse)
    add_id(evidence, TOOL_NAME, "table", table)
    columns = list(payload.get("columns") or [])
    rows = list(payload.get("rows") or [])
    add_number(evidence, TOOL_NAME, "row_count", int(payload.get("row_count", len(rows))))

    records: list[dict[str, Any]] = []
    for i, row in enumerate(rows):
        rec = {columns[j]: row[j] for j in range(min(len(columns), len(row)))}
        records.append(rec)
        if "asset_id" in rec:
            add_id(evidence, TOOL_NAME, f"asset_id:{i}", str(rec["asset_id"]))
        if "ping_count" in rec:
            key = f"ping_count:{rec.get('asset_id', i)}"
            add_number(evidence, TOOL_NAME, key, rec["ping_count"])

    return {
        "tool": TOOL_NAME,
        "warehouse": warehouse,
        "table": table,
        "columns": columns,
        "rows": records,
        "row_count": len(records),
        "raw": payload,
    }
