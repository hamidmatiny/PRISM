"""Per-asset circuit breaker FSM: closed -> open -> half_open -> closed.

Exact state shape from Argus's incident-engine, ported to Python (the FSM and
API shape matter more than matching Argus's Go implementation language):
cooldown-gated reopen probe, auto-resolve on recovery, same-incident-id
refresh on retrip rather than minting a new incident. Scoped per asset_id —
tripping one asset's breaker never touches any other asset's state.
"""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass, field
from datetime import datetime

from prism_incident_engine.timeutil import now_utc
from prism_incident_engine.trip_policies import TripPolicies

BreakerState = str  # "closed" | "open" | "half_open"


@dataclass
class AssetBreaker:
    asset_id: str
    policies: TripPolicies
    state: BreakerState = "closed"
    incident_id: str | None = None
    trip_reason: str | None = None
    opened_at: datetime | None = None
    last_transition_at: datetime = field(default_factory=now_utc)
    ingestion_window: deque[bool] = field(default_factory=lambda: deque(maxlen=1))
    consecutive_qa_failures: int = 0
    drifted_feature_count: int = 0

    def __post_init__(self) -> None:
        self.ingestion_window = deque(maxlen=self.policies.quarantine_rate_window)

    # -- observation intake -------------------------------------------------

    def record_ingestion_outcome(self, *, quarantined: bool) -> None:
        self.ingestion_window.append(quarantined)

    def record_qa_outcome(self, *, passed: bool) -> None:
        self.consecutive_qa_failures = 0 if passed else self.consecutive_qa_failures + 1

    def record_drift(self, *, drifted_feature_count: int) -> None:
        # No producer exists until Phase 16's drift-monitor ships "drift"
        # observations (ADR-005: correctly implemented, dormant, not faked).
        self.drifted_feature_count = drifted_feature_count

    def clear_counters(self) -> None:
        self.ingestion_window.clear()
        self.consecutive_qa_failures = 0
        self.drifted_feature_count = 0

    # -- trip evaluation ------------------------------------------------

    @property
    def quarantine_rate(self) -> float | None:
        if len(self.ingestion_window) < self.policies.quarantine_rate_window:
            return None
        return sum(self.ingestion_window) / len(self.ingestion_window)

    def tripped_policy(self) -> str | None:
        """Return the name of the first policy currently in violation, or None."""
        rate = self.quarantine_rate
        if rate is not None and rate > self.policies.quarantine_rate_threshold:
            return "quarantine_rate"
        if self.consecutive_qa_failures >= self.policies.consecutive_qa_failures_threshold:
            return "consecutive_qa_failures"
        if self.drifted_feature_count >= self.policies.drifted_features_threshold:
            return "drifted_features"
        return None

    # -- cooldown / probe -----------------------------------------------

    def cooldown_elapsed(self) -> bool:
        if self.state != "open" or self.opened_at is None:
            return False
        return (now_utc() - self.opened_at).total_seconds() >= self.policies.cooldown_seconds

    def maybe_enter_half_open(self) -> bool:
        """Lazy cooldown check, called before processing any new observation
        or serving a breakers-list read. Returns True if a transition happened."""
        if self.state == "open" and self.cooldown_elapsed():
            self.state = "half_open"
            self.last_transition_at = now_utc()
            return True
        return False

    def to_dict(self) -> dict:
        return {
            "asset_id": self.asset_id,
            "state": self.state,
            "incident_id": self.incident_id,
            "trip_reason": self.trip_reason,
            "quarantine_rate": self.quarantine_rate,
            "consecutive_qa_failures": self.consecutive_qa_failures,
            "drifted_feature_count": self.drifted_feature_count,
            "opened_at": self.opened_at.isoformat().replace("+00:00", "Z")
            if self.opened_at
            else None,
            "last_transition_at": self.last_transition_at.isoformat().replace("+00:00", "Z"),
        }
