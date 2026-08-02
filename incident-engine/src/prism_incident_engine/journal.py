"""Append-only incident/breaker audit journal (JSONL).

Unlike scenario-engine's per-scenario-id journal (Phase 12, truncated on open
so a re-run with the same id is a fresh replay), this journal is a permanent,
continuously-appended audit trail: every breaker transition and every
incident lifecycle event, forever, across restarts. Breaker *state* itself
lives in memory (see store.py) and resets on restart — the journal is what
makes a run auditable after the fact even though live state doesn't survive
a restart, same trade-off every other PRISM service makes for local-first
simplicity (ADR-001).
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class JournalEntry:
    # "breaker_transition" | "incident_opened" | "incident_acknowledged" |
    # "incident_resolved" | "observation"
    event: str
    asset_id: str
    at: str
    detail: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class IncidentJournal:
    def __init__(self, path: Path) -> None:
        self.path = path
        self.path.parent.mkdir(parents=True, exist_ok=True)
        if not self.path.exists():
            self.path.write_text("", encoding="utf-8")

    def append(self, event: str, *, asset_id: str, detail: dict[str, Any]) -> JournalEntry:
        entry = JournalEntry(
            event=event,
            asset_id=asset_id,
            at=datetime.now(tz=UTC).isoformat().replace("+00:00", "Z"),
            detail=detail,
        )
        with self.path.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(entry.to_dict(), sort_keys=True) + "\n")
        return entry

    def tail(self, limit: int = 100) -> list[dict[str, Any]]:
        if not self.path.exists():
            return []
        lines = self.path.read_text(encoding="utf-8").splitlines()
        return [json.loads(line) for line in lines[-limit:]]
