"""Runtime configuration for incident-engine (local-first, ADR-001)."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class IncidentConfig:
    host: str = "0.0.0.0"
    port: int = 9108
    data_root: Path = Path(".data")
    policies_path: Path | None = None  # None -> packaged default_policies.yaml

    @property
    def journal_path(self) -> Path:
        return self.data_root / "incident-engine" / "journal" / "incidents.jsonl"

    @property
    def webhook_inbox_path(self) -> Path:
        return self.data_root / "incident-engine" / "webhook-inbox.jsonl"

    @classmethod
    def from_env(cls) -> IncidentConfig:
        policies_raw = os.getenv("PRISM_INCIDENT_POLICIES", "").strip()
        return cls(
            host=os.getenv("PRISM_HEALTH_HOST", "0.0.0.0"),
            port=int(os.getenv("PRISM_INCIDENT_ENGINE_PORT", "9108")),
            data_root=Path(os.getenv("PRISM_DATA_ROOT", ".data")),
            policies_path=Path(policies_raw) if policies_raw else None,
        )
