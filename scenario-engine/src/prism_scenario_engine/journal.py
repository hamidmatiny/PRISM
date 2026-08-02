"""Append-only scenario audit journal (JSONL)."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class JournalEntry:
    scenario_id: str
    seed: int
    tick: int
    asset_id: str
    outcome: str
    event_id: str | None
    kind: str | None
    emitted: bool

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class ScenarioJournal:
    """One JSONL file per scenario_id — deterministic content for a fixed seed."""

    def __init__(self, journal_dir: Path, scenario_id: str) -> None:
        self.path = journal_dir / f"{scenario_id}.jsonl"
        self.path.parent.mkdir(parents=True, exist_ok=True)
        # Truncate on open so a restart with the same scenario_id is a fresh replay.
        self.path.write_text("", encoding="utf-8")

    def append(self, entry: JournalEntry) -> None:
        with self.path.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(entry.to_dict(), sort_keys=True) + "\n")
