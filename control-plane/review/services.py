"""Sync pending queue → ORM and apply review decisions."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from django.contrib.auth.models import User
from django.db import transaction
from django.utils.dateparse import parse_datetime

from audit.services import record_audit
from fleet.models import Asset
from prism_cv_finding_schema import CvFinding, DefectClass
from review.models import InspectionFinding, ReviewDecision
from review.queue import list_pending_envelopes, load_pending_envelope, move_to_decided
from review.tasks import enqueue_gold_writeback


def _parse_ts(value: str | datetime) -> datetime:
    if isinstance(value, datetime):
        return value
    parsed = parse_datetime(value.replace("Z", "+00:00"))
    if parsed is None:
        raise ValueError(f"invalid timestamp: {value}")
    return parsed


def sync_pending_queue(*, actor: User | None = None) -> dict[str, Any]:
    """
    Read actual cv-review-queue/pending/*.json files and upsert InspectionFinding rows.
    """
    created = 0
    updated = 0
    envelopes = list_pending_envelopes()
    for envelope in envelopes:
        finding_payload = envelope["finding"]
        asset, _ = Asset.objects.get_or_create(
            asset_id=finding_payload["asset_id"],
            defaults={"name": finding_payload["asset_id"]},
        )
        defaults = {
            "asset": asset,
            "frame_ref": finding_payload["frame_ref"],
            "defect_class": finding_payload["defect_class"],
            "confidence": finding_payload["confidence"],
            "bounding_box": finding_payload.get("bounding_box"),
            "model_id": finding_payload.get("model_id", ""),
            "detected_at": _parse_ts(finding_payload["detected_at"]),
            "reviewed": bool(finding_payload.get("reviewed", False)),
            "queue_status": InspectionFinding.QueueStatus.PENDING,
            "queue_path": envelope.get("_path", ""),
            "queue_reason": envelope.get("reason", ""),
            "payload": finding_payload,
        }
        obj, was_created = InspectionFinding.objects.update_or_create(
            finding_id=finding_payload["finding_id"],
            defaults=defaults,
        )
        if was_created:
            created += 1
        else:
            updated += 1

    record_audit(
        actor=actor,
        action="review_queue.sync",
        object_type="cv-review-queue",
        object_id="pending",
        after={"created": created, "updated": updated, "pending_files": len(envelopes)},
    )
    return {"created": created, "updated": updated, "pending_files": len(envelopes)}


@transaction.atomic
def apply_decision(
    *,
    finding_id: str,
    decision: str,
    reviewer: User,
    notes: str = "",
    relabel_class: str = "",
) -> ReviewDecision:
    """Approve / reject / relabel a pending finding from the live queue."""
    if decision not in {
        ReviewDecision.Decision.APPROVE,
        ReviewDecision.Decision.REJECT,
        ReviewDecision.Decision.RELABEL,
    }:
        raise ValueError(f"invalid decision: {decision}")
    if decision == ReviewDecision.Decision.RELABEL:
        if not relabel_class:
            raise ValueError("relabel_class is required for relabel")
        # Validate against contract enum.
        DefectClass(relabel_class)

    # Prefer live pending file; fall back to already-synced ORM row.
    try:
        envelope = load_pending_envelope(finding_id)
        payload = envelope["finding"]
    except FileNotFoundError:
        finding = InspectionFinding.objects.select_for_update().get(finding_id=finding_id)
        payload = finding.payload
        envelope = None

    asset, _ = Asset.objects.get_or_create(
        asset_id=payload["asset_id"],
        defaults={"name": payload["asset_id"]},
    )
    finding, _ = InspectionFinding.objects.select_for_update().get_or_create(
        finding_id=finding_id,
        defaults={
            "asset": asset,
            "frame_ref": payload["frame_ref"],
            "defect_class": payload["defect_class"],
            "confidence": payload["confidence"],
            "bounding_box": payload.get("bounding_box"),
            "model_id": payload.get("model_id", ""),
            "detected_at": _parse_ts(payload["detected_at"]),
            "payload": payload,
            "queue_path": (envelope or {}).get("_path", ""),
            "queue_reason": (envelope or {}).get("reason", ""),
        },
    )

    before = {
        "queue_status": finding.queue_status,
        "reviewed": finding.reviewed,
        "defect_class": finding.defect_class,
    }

    if decision == ReviewDecision.Decision.APPROVE:
        finding.queue_status = InspectionFinding.QueueStatus.APPROVED
        finding.reviewed = True
    elif decision == ReviewDecision.Decision.REJECT:
        finding.queue_status = InspectionFinding.QueueStatus.REJECTED
        finding.reviewed = True
    else:
        finding.queue_status = InspectionFinding.QueueStatus.RELABELED
        finding.defect_class = relabel_class
        finding.reviewed = True
        payload = {**payload, "defect_class": relabel_class}

    payload = {**payload, "reviewed": True, "defect_class": finding.defect_class}
    # Re-validate against contract before persisting.
    validated = CvFinding.model_validate(payload)
    finding.payload = validated.to_payload()
    finding.save()

    review = ReviewDecision.objects.create(
        finding=finding,
        decision=decision,
        relabel_class=relabel_class if decision == ReviewDecision.Decision.RELABEL else "",
        notes=notes,
        reviewer=reviewer,
    )

    if envelope is not None:
        move_to_decided(finding_id)

    record_audit(
        actor=reviewer,
        action=f"review_decision.{decision}",
        object_type="InspectionFinding",
        object_id=finding_id,
        before=before,
        after={
            "queue_status": finding.queue_status,
            "reviewed": finding.reviewed,
            "defect_class": finding.defect_class,
            "decision_id": review.pk,
        },
        metadata={"notes": notes, "relabel_class": relabel_class},
    )

    # Approved + relabeled findings write reviewed=true into the gold findings zone.
    if decision in {ReviewDecision.Decision.APPROVE, ReviewDecision.Decision.RELABEL}:
        enqueue_gold_writeback(finding.finding_id)

    return review
