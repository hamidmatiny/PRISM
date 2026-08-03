"""Per-asset circuit breaker FSM: closed -> open -> half_open -> closed.

Exact state shape from Argus's incident-engine, ported to Python (the FSM and
API shape matter more than matching Argus's Go implementation language):
cooldown-gated reopen probe, auto-resolve on recovery, same-incident-id
refresh on retrip rather than minting a new incident. Scoped per asset_id —
tripping one asset's breaker never touches any other asset's state.

Phase 18: trip *thresholds* are evaluated by OPA/Rego (see
``policies/rego/*.rego``). This module still owns the rolling window / counters
and the cooldown FSM; ``tripped_policy()`` asks the policy engine.
"""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass, field
from datetime import datetime
from typing import TYPE_CHECKING

from prism_incident_engine.timeutil import now_utc
from prism_incident_engine.trip_policies import TripPolicies

if TYPE_CHECKING:
    from prism_incident_engine.opa_client import PolicyEngine

BreakerState = str  # "closed" | "open" | "half_open"


@dataclass
class AssetBreaker:
    asset_id: str
    policies: TripPolicies
    policy_engine: PolicyEngine
    state: BreakerState = "closed"
    incident_id: str | None = None
    trip_reason: str | None = None
    opened_at: datetime | None = None
    last_transition_at: datetime = field(default_factory=now_utc)
    ingestion_window: deque[bool] = field(default_factory=lambda: deque(maxlen=1))
    consecutive_qa_failures: int = 0
    drifted_feature_count: int = 0
    last_policy_error: str | None = None

    def __post_init__(self) -> None:
        self.ingestion_window = deque(maxlen=self.policies.quarantine_rate_window)

    # -- observation intake -------------------------------------------------

    def record_ingestion_outcome(self, *, quarantined: bool) -> None:
        self.ingestion_window.append(quarantined)

    def record_qa_outcome(self, *, passed: bool) -> None:
        self.consecutive_qa_failures = 0 if passed else self.consecutive_qa_failures + 1

    def record_drift(self, *, drifted_feature_count: int) -> None:
        self.drifted_feature_count = drifted_feature_count

    def clear_counters(self) -> None:
        self.ingestion_window.clear()
        self.consecutive_qa_failures = 0
        self.drifted_feature_count = 0
        self.last_policy_error = None

    # -- trip evaluation ------------------------------------------------

    @property
    def quarantine_rate(self) -> float | None:
        if len(self.ingestion_window) < self.policies.quarantine_rate_window:
            return None
        return sum(self.ingestion_window) / len(self.ingestion_window)

    def policy_input(self) -> dict:
        return {
            "quarantine_window": list(self.ingestion_window),
            "consecutive_qa_failures": self.consecutive_qa_failures,
            "drifted_feature_count": self.drifted_feature_count,
        }

    def tripped_policy(self) -> str | None:
        """Return the name of the first Rego policy currently in violation, or None.

        When the policy engine is unreachable, returns None (fail-open) and
        records ``last_policy_error`` — never silently re-implements thresholds
        in Python.
        """
        decision = self.policy_engine.evaluate_trip(self.policy_input())
        self.last_policy_error = decision.error
        if not decision.ready:
            return None
        if decision.trip:
            return decision.reason
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
            "policy_engine_error": self.last_policy_error,
        }
