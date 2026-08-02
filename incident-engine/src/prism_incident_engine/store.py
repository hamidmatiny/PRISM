"""Orchestrates breakers + incidents + audit journal + mock webhook delivery."""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Literal

from prism_incident_engine.fsm import AssetBreaker
from prism_incident_engine.journal import IncidentJournal
from prism_incident_engine.timeutil import now_utc
from prism_incident_engine.trip_policies import TripPolicies
from prism_incident_engine.webhook import WebhookSender

ObservationKind = Literal[
    "ingestion_accepted", "ingestion_quarantined", "qa_pass", "qa_fail", "drift"
]
IncidentStatus = Literal["open", "acknowledged", "resolved"]


@dataclass
class Incident:
    incident_id: str
    asset_id: str
    trigger: str
    status: IncidentStatus = "open"
    trip_count: int = 1
    opened_at: datetime = field(default_factory=now_utc)
    last_transition_at: datetime = field(default_factory=now_utc)
    acknowledged_at: datetime | None = None
    resolved_at: datetime | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "incident_id": self.incident_id,
            "asset_id": self.asset_id,
            "trigger": self.trigger,
            "status": self.status,
            "trip_count": self.trip_count,
            "opened_at": self.opened_at.isoformat().replace("+00:00", "Z"),
            "last_transition_at": self.last_transition_at.isoformat().replace("+00:00", "Z"),
            "acknowledged_at": self.acknowledged_at.isoformat().replace("+00:00", "Z")
            if self.acknowledged_at
            else None,
            "resolved_at": self.resolved_at.isoformat().replace("+00:00", "Z")
            if self.resolved_at
            else None,
        }


class IncidentStore:
    def __init__(
        self, policies: TripPolicies, journal: IncidentJournal, webhook: WebhookSender
    ) -> None:
        self.policies = policies
        self.journal = journal
        self.webhook = webhook
        self._breakers: dict[str, AssetBreaker] = {}
        self._incidents: dict[str, Incident] = {}

    # -- accessors --------------------------------------------------------

    def breaker(self, asset_id: str) -> AssetBreaker:
        b = self._breakers.get(asset_id)
        if b is None:
            b = AssetBreaker(asset_id=asset_id, policies=self.policies)
            self._breakers[asset_id] = b
        return b

    def all_breakers(self) -> list[dict[str, Any]]:
        for b in self._breakers.values():
            self.refresh_breaker_cooldown(b)
        return [b.to_dict() for b in self._breakers.values()]

    def incidents(self, status: str | None = None) -> list[dict[str, Any]]:
        items = list(self._incidents.values())
        if status:
            items = [i for i in items if i.status == status]
        items.sort(key=lambda i: i.last_transition_at, reverse=True)
        return [i.to_dict() for i in items]

    def incident(self, incident_id: str) -> Incident | None:
        return self._incidents.get(incident_id)

    # -- cooldown -----------------------------------------------------------

    def refresh_breaker_cooldown(self, breaker: AssetBreaker) -> None:
        if breaker.maybe_enter_half_open():
            self.journal.append(
                "breaker_transition",
                asset_id=breaker.asset_id,
                detail={"from": "open", "to": "half_open", "reason": "cooldown_elapsed"},
            )

    # -- observation intake ---------------------------------------------

    def record_observation(
        self, asset_id: str, kind: ObservationKind, detail: dict[str, Any] | None = None
    ) -> dict[str, Any]:
        breaker = self.breaker(asset_id)
        self.refresh_breaker_cooldown(breaker)
        was_half_open = breaker.state == "half_open"

        if kind == "ingestion_accepted":
            breaker.record_ingestion_outcome(quarantined=False)
        elif kind == "ingestion_quarantined":
            breaker.record_ingestion_outcome(quarantined=True)
        elif kind == "qa_pass":
            breaker.record_qa_outcome(passed=True)
        elif kind == "qa_fail":
            breaker.record_qa_outcome(passed=False)
        elif kind == "drift":
            breaker.record_drift(
                drifted_feature_count=int((detail or {}).get("drifted_feature_count", 0))
            )

        self.journal.append(
            "observation", asset_id=asset_id, detail={"kind": kind, **(detail or {})}
        )

        tripped = breaker.tripped_policy()

        if was_half_open:
            # Textbook single-probe semantics: the *one* observation that
            # arrives in half_open decides pass/fail on its own -- not a
            # blend with stale pre-trip history still sitting in the
            # rolling window. A single good sample should be able to start
            # recovery; a single bad one should retrip immediately.
            probe_ok = kind in {"ingestion_accepted", "qa_pass"} or (
                kind == "drift" and tripped is None
            )
            self._resolve_probe(breaker, ok=probe_ok)
        elif breaker.state == "closed" and tripped is not None:
            self._trip(breaker, reason=tripped)
        elif breaker.state == "open" and tripped is not None:
            # Still-bad evidence while already open: refresh the existing
            # incident rather than minting a new one (same behavior as a
            # half_open retrip -- the incident just keeps accumulating proof).
            self._refresh_incident(breaker, reason=tripped)

        return breaker.to_dict()

    # -- transitions ------------------------------------------------------

    def _trip(self, breaker: AssetBreaker, *, reason: str) -> None:
        breaker.state = "open"
        breaker.trip_reason = reason
        breaker.opened_at = now_utc()
        breaker.last_transition_at = breaker.opened_at
        incident_id = breaker.incident_id or f"inc_{uuid.uuid4().hex[:12]}"
        is_new = breaker.incident_id is None
        breaker.incident_id = incident_id
        if is_new:
            self._incidents[incident_id] = Incident(
                incident_id=incident_id, asset_id=breaker.asset_id, trigger=reason
            )
            self.journal.append(
                "incident_opened",
                asset_id=breaker.asset_id,
                detail={"incident_id": incident_id, "trigger": reason},
            )
            self.webhook.notify(
                {
                    "event": "incident_opened",
                    "incident_id": incident_id,
                    "asset_id": breaker.asset_id,
                    "trigger": reason,
                }
            )
        self.journal.append(
            "breaker_transition",
            asset_id=breaker.asset_id,
            detail={"from": "closed", "to": "open", "reason": reason},
        )

    def _refresh_incident(self, breaker: AssetBreaker, *, reason: str) -> None:
        incident = self._incidents.get(breaker.incident_id or "")
        if incident is None:
            self._trip(breaker, reason=reason)
            return
        incident.trip_count += 1
        incident.last_transition_at = now_utc()
        incident.trigger = reason
        breaker.trip_reason = reason
        breaker.last_transition_at = incident.last_transition_at
        self.journal.append(
            "incident_opened",
            asset_id=breaker.asset_id,
            detail={
                "incident_id": incident.incident_id,
                "trigger": reason,
                "retrip": True,
                "trip_count": incident.trip_count,
            },
        )

    def _resolve_probe(self, breaker: AssetBreaker, *, ok: bool) -> None:
        if ok:
            breaker.state = "closed"
            breaker.last_transition_at = now_utc()
            breaker.trip_reason = None
            breaker.clear_counters()
            incident = self._incidents.get(breaker.incident_id or "")
            if incident is not None:
                incident.status = "resolved"
                incident.resolved_at = now_utc()
                incident.last_transition_at = incident.resolved_at
                self.journal.append(
                    "incident_resolved",
                    asset_id=breaker.asset_id,
                    detail={"incident_id": incident.incident_id, "reason": "probe_passed"},
                )
            self.journal.append(
                "breaker_transition",
                asset_id=breaker.asset_id,
                detail={"from": "half_open", "to": "closed", "reason": "probe_passed"},
            )
            breaker.incident_id = None
        else:
            # Probe failed: the same problem that opened the breaker is
            # still present -- prefer the established trip_reason over a
            # possibly-noisy instantaneous re-evaluation of the (still
            # window-blended) tripped_policy().
            self._refresh_incident(
                breaker, reason=breaker.trip_reason or breaker.tripped_policy() or "unknown"
            )
            breaker.state = "open"
            breaker.opened_at = now_utc()
            self.journal.append(
                "breaker_transition",
                asset_id=breaker.asset_id,
                detail={"from": "half_open", "to": "open", "reason": "probe_failed"},
            )

    # -- manual overrides -----------------------------------------------

    def acknowledge(self, incident_id: str) -> Incident | None:
        incident = self._incidents.get(incident_id)
        if incident is None:
            return None
        incident.status = "acknowledged"
        incident.acknowledged_at = now_utc()
        incident.last_transition_at = incident.acknowledged_at
        self.journal.append(
            "incident_acknowledged", asset_id=incident.asset_id, detail={"incident_id": incident_id}
        )
        return incident

    def resolve(self, incident_id: str) -> Incident | None:
        incident = self._incidents.get(incident_id)
        if incident is None:
            return None
        incident.status = "resolved"
        incident.resolved_at = now_utc()
        incident.last_transition_at = incident.resolved_at
        breaker = self._breakers.get(incident.asset_id)
        if breaker is not None:
            breaker.state = "closed"
            breaker.incident_id = None
            breaker.trip_reason = None
            breaker.last_transition_at = now_utc()
            breaker.clear_counters()
        self.journal.append(
            "incident_resolved",
            asset_id=incident.asset_id,
            detail={"incident_id": incident_id, "reason": "manual"},
        )
        self.journal.append(
            "breaker_transition",
            asset_id=incident.asset_id,
            detail={"to": "closed", "reason": "manual_resolve"},
        )
        return incident
