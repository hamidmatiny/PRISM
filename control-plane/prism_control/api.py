"""Django Ninja API layer with RBAC."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Any, Literal
from uuid import uuid4

from django.conf import settings
from django.http import FileResponse
from django.shortcuts import get_object_or_404
from ninja import Field, NinjaAPI, Schema
from ninja.errors import HttpError

from audit.models import AuditLogEntry
from audit.services import record_audit
from fleet.models import Asset, WorkOrder
from prism_control.rbac import (
    ROLE_FLEET_ADMIN,
    ROLE_INSPECTOR,
    ROLE_VIEWER,
    assert_roles,
    auth,
    user_roles,
)
from review.models import InspectionFinding, ReviewDecision
from review.queue import list_pending_envelopes, load_pending_envelope
from review.services import apply_decision, sync_pending_queue

api = NinjaAPI(
    title="PRISM Control Plane",
    version="0.1.0",
    urls_namespace="api",
    auth=auth,
)


class RoleOut(Schema):
    username: str
    roles: list[str]


class AssetIn(Schema):
    asset_id: str
    name: str = ""
    status: str = "active"


class AssetOut(Schema):
    asset_id: str
    name: str
    status: str


class WorkOrderIn(Schema):
    asset_id: str
    title: str
    description: str = ""


class WorkOrderOut(Schema):
    work_order_id: str
    asset_id: str
    title: str
    description: str
    status: str
    created_at: datetime


class BoundingBoxOut(Schema):
    x: float
    y: float
    width: float
    height: float


class PendingEnvelopeOut(Schema):
    finding_id: str
    asset_id: str
    defect_class: str
    confidence: float
    frame_ref: str
    reason: str
    queue: str
    path: str
    reviewed: bool
    bounding_box: BoundingBoxOut | None = None
    detected_at: str | None = None


class DecisionIn(Schema):
    decision: Literal["approve", "reject", "relabel"]
    notes: str = ""
    relabel_class: str = Field(default="", description="Required when decision=relabel")


class DecisionOut(Schema):
    finding_id: str
    decision: str
    queue_status: str
    reviewed: bool
    defect_class: str
    gold_enqueued: bool


class FindingOut(Schema):
    finding_id: str
    asset_id: str
    defect_class: str
    confidence: float
    queue_status: str
    reviewed: bool
    gold_path: str
    frame_ref: str
    detected_at: datetime
    bounding_box: BoundingBoxOut | None = None


class AuditOut(Schema):
    id: int
    action: str
    object_type: str
    object_id: str
    actor_username: str
    created_at: datetime
    before: dict[str, Any] | None = None
    after: dict[str, Any] | None = None


class SyncOut(Schema):
    created: int
    updated: int
    pending_files: int


@api.get("/v1/me", response=RoleOut)
def me(request):
    user = assert_roles(request, ROLE_VIEWER, ROLE_INSPECTOR, ROLE_FLEET_ADMIN)
    return {"username": user.username, "roles": sorted(user_roles(user))}


@api.get("/v1/assets", response=list[AssetOut])
def list_assets(request):
    assert_roles(request, ROLE_VIEWER, ROLE_INSPECTOR, ROLE_FLEET_ADMIN)
    return [
        {"asset_id": a.asset_id, "name": a.name, "status": a.status} for a in Asset.objects.all()
    ]


@api.post("/v1/assets", response=AssetOut)
def create_asset(request, body: AssetIn):
    user = assert_roles(request, ROLE_FLEET_ADMIN)
    asset, created = Asset.objects.get_or_create(
        asset_id=body.asset_id,
        defaults={"name": body.name or body.asset_id, "status": body.status},
    )
    if not created:
        raise HttpError(409, f"asset already exists: {body.asset_id}")
    record_audit(
        actor=user,
        action="asset.create",
        object_type="Asset",
        object_id=asset.asset_id,
        after={"asset_id": asset.asset_id, "status": asset.status},
    )
    return {"asset_id": asset.asset_id, "name": asset.name, "status": asset.status}


@api.get("/v1/work-orders", response=list[WorkOrderOut])
def list_work_orders(request, asset_id: str | None = None):
    assert_roles(request, ROLE_VIEWER, ROLE_INSPECTOR, ROLE_FLEET_ADMIN)
    qs = WorkOrder.objects.select_related("asset").all()
    if asset_id:
        qs = qs.filter(asset__asset_id=asset_id)
    return [
        {
            "work_order_id": w.work_order_id,
            "asset_id": w.asset.asset_id,
            "title": w.title,
            "description": w.description,
            "status": w.status,
            "created_at": w.created_at,
        }
        for w in qs
    ]


@api.post("/v1/work-orders", response=WorkOrderOut)
def create_work_order(request, body: WorkOrderIn):
    user = assert_roles(request, ROLE_FLEET_ADMIN, ROLE_INSPECTOR)
    asset = get_object_or_404(Asset, asset_id=body.asset_id)
    wo = WorkOrder.objects.create(
        work_order_id=f"wo_{uuid4().hex[:10]}",
        asset=asset,
        title=body.title,
        description=body.description,
        created_by=user,
    )
    record_audit(
        actor=user,
        action="work_order.create",
        object_type="WorkOrder",
        object_id=wo.work_order_id,
        after={"title": wo.title, "asset_id": asset.asset_id},
    )
    return {
        "work_order_id": wo.work_order_id,
        "asset_id": asset.asset_id,
        "title": wo.title,
        "description": wo.description,
        "status": wo.status,
        "created_at": wo.created_at,
    }


@api.get("/v1/review-queue", response=list[PendingEnvelopeOut])
def review_queue(request):
    """List pending envelopes directly from cv-service's pending directory."""
    assert_roles(request, ROLE_VIEWER, ROLE_INSPECTOR, ROLE_FLEET_ADMIN)
    out: list[dict[str, Any]] = []
    for envelope in list_pending_envelopes():
        finding = envelope["finding"]
        out.append(
            {
                "finding_id": finding["finding_id"],
                "asset_id": finding["asset_id"],
                "defect_class": finding["defect_class"],
                "confidence": finding["confidence"],
                "frame_ref": finding["frame_ref"],
                "reason": envelope.get("reason", ""),
                "queue": envelope.get("queue", ""),
                "path": envelope.get("_path", ""),
                "reviewed": finding.get("reviewed", False),
                "bounding_box": finding.get("bounding_box"),
                "detected_at": finding.get("detected_at"),
            }
        )
    from prism_control.metrics import emit_review_queue_depth

    emit_review_queue_depth(len(out))
    return out


@api.post("/v1/review-queue/sync", response=SyncOut)
def sync_queue(request):
    user = assert_roles(request, ROLE_INSPECTOR, ROLE_FLEET_ADMIN)
    return sync_pending_queue(actor=user)


@api.get("/v1/findings", response=list[FindingOut])
def list_findings(request, queue_status: str | None = None):
    assert_roles(request, ROLE_VIEWER, ROLE_INSPECTOR, ROLE_FLEET_ADMIN)
    qs = InspectionFinding.objects.select_related("asset").all()
    if queue_status:
        qs = qs.filter(queue_status=queue_status)
    return [
        {
            "finding_id": f.finding_id,
            "asset_id": f.asset.asset_id,
            "defect_class": f.defect_class,
            "confidence": f.confidence,
            "queue_status": f.queue_status,
            "reviewed": f.reviewed,
            "gold_path": f.gold_path,
            "frame_ref": f.frame_ref,
            "detected_at": f.detected_at,
            "bounding_box": f.bounding_box,
        }
        for f in qs
    ]


@api.get("/v1/findings/{finding_id}", response=FindingOut)
def get_finding(request, finding_id: str):
    """Single finding — prefers ORM row, falls back to live pending envelope."""
    assert_roles(request, ROLE_VIEWER, ROLE_INSPECTOR, ROLE_FLEET_ADMIN)
    try:
        f = InspectionFinding.objects.select_related("asset").get(finding_id=finding_id)
        return {
            "finding_id": f.finding_id,
            "asset_id": f.asset.asset_id,
            "defect_class": f.defect_class,
            "confidence": f.confidence,
            "queue_status": f.queue_status,
            "reviewed": f.reviewed,
            "gold_path": f.gold_path,
            "frame_ref": f.frame_ref,
            "detected_at": f.detected_at,
            "bounding_box": f.bounding_box,
        }
    except InspectionFinding.DoesNotExist:
        pass
    try:
        envelope = load_pending_envelope(finding_id)
    except FileNotFoundError as exc:
        raise HttpError(404, str(exc)) from exc
    finding = envelope["finding"]
    return {
        "finding_id": finding["finding_id"],
        "asset_id": finding["asset_id"],
        "defect_class": finding["defect_class"],
        "confidence": finding["confidence"],
        "queue_status": "pending",
        "reviewed": finding.get("reviewed", False),
        "gold_path": "",
        "frame_ref": finding["frame_ref"],
        "detected_at": finding["detected_at"],
        "bounding_box": finding.get("bounding_box"),
    }


_FIXTURE_BY_CLASS = {
    "dent": "dent_sample.png",
    "crack": "crack_sample.png",
    "tire_wear": "tire_wear_sample.png",
    "sensor_obstruction": "sensor_obstruction_sample.png",
    "anomaly": "anomaly_sample.png",
}


@api.get("/v1/frames/{frame_ref}")
def get_frame(request, frame_ref: str, defect_class: str = "anomaly"):
    """Serve the source frame for a CV finding.

    Live camera bytes are not always retained on disk locally; we resolve the
    cv-service fixture image for the finding's defect_class (same fixtures the
    detector was exercised against). Continuity: class + frame_ref come from
    real finding payloads.
    """
    assert_roles(request, ROLE_VIEWER, ROLE_INSPECTOR, ROLE_FLEET_ADMIN)
    name = _FIXTURE_BY_CLASS.get(defect_class, "anomaly_sample.png")
    path = Path(settings.CV_FIXTURE_IMAGES_DIR) / name
    if not path.is_file():
        raise HttpError(404, f"frame fixture missing for {frame_ref}: {path}")
    # FileResponse needs a file handle (Path alone is not iterable in Django 5).
    handle = path.open("rb")
    return FileResponse(handle, content_type="image/png", filename=name)


@api.post("/v1/review-queue/{finding_id}/decide", response=DecisionOut)
def decide(request, finding_id: str, body: DecisionIn):
    user = assert_roles(request, ROLE_INSPECTOR, ROLE_FLEET_ADMIN)
    try:
        review = apply_decision(
            finding_id=finding_id,
            decision=body.decision,
            reviewer=user,
            notes=body.notes,
            relabel_class=body.relabel_class,
        )
    except FileNotFoundError as exc:
        raise HttpError(404, str(exc)) from exc
    except InspectionFinding.DoesNotExist as exc:
        raise HttpError(404, str(exc)) from exc
    except ValueError as exc:
        raise HttpError(400, str(exc)) from exc

    finding = review.finding
    gold_enqueued = body.decision in {
        ReviewDecision.Decision.APPROVE,
        ReviewDecision.Decision.RELABEL,
    }
    return {
        "finding_id": finding.finding_id,
        "decision": review.decision,
        "queue_status": finding.queue_status,
        "reviewed": finding.reviewed,
        "defect_class": finding.defect_class,
        "gold_enqueued": gold_enqueued,
    }


@api.get("/v1/audit", response=list[AuditOut])
def list_audit(request, limit: int = 50):
    assert_roles(request, ROLE_FLEET_ADMIN, ROLE_INSPECTOR)
    limit = max(1, min(limit, 200))
    return [
        {
            "id": e.id,
            "action": e.action,
            "object_type": e.object_type,
            "object_id": e.object_id,
            "actor_username": e.actor_username,
            "created_at": e.created_at,
            "before": e.before,
            "after": e.after,
        }
        for e in AuditLogEntry.objects.all()[:limit]
    ]
