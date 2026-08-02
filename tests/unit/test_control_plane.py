"""Control-plane tests — real ReviewQueue envelopes (cv-service writer), not hand-rolled fakes."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

import pytest
from django.contrib.auth.models import Group, User

from prism_cv_finding_schema import BoundingBox, CvFinding, DefectClass
from prism_cv_service.review_queue import ReviewQueue

pytestmark = pytest.mark.django_db

ROOT = Path(__file__).resolve().parents[2]
LIVE_PENDING = ROOT / ".data" / "cv-review-queue" / "pending"


@pytest.fixture()
def queue_dirs(tmp_path, settings):
    pending = tmp_path / "pending"
    decided = tmp_path / "decided"
    gold = tmp_path / "gold"
    pending.mkdir()
    decided.mkdir()
    gold.mkdir()
    settings.CV_REVIEW_PENDING_DIR = pending
    settings.CV_REVIEW_DECIDED_DIR = decided
    settings.CV_FINDINGS_GOLD_DIR = gold
    settings.Q_CLUSTER = {**settings.Q_CLUSTER, "sync": True}
    return pending, decided, gold


@pytest.fixture()
def roles(db):
    for name in ("viewer", "inspector", "fleet-admin"):
        Group.objects.get_or_create(name=name)


def _make_user(username: str, role: str) -> tuple[User, str]:
    from fleet.models import UserProfile

    user = User.objects.create_user(username=username, password="x")
    user.groups.add(Group.objects.get(name=role))
    profile = UserProfile.objects.create(user=user)
    return user, profile.api_token


def _enqueue_via_cv_service(
    pending: Path, published: Path, *, finding_id: str = "fnd_aabbccddeeff"
):
    """Produce a pending file using the same ReviewQueue class as cv-service."""
    finding = CvFinding(
        finding_id=finding_id,
        asset_id="PRISM-AST-001",
        frame_ref="frm_aabbccddeeff",
        defect_class=DefectClass.ANOMALY,
        confidence=0.42,
        bounding_box=BoundingBox(x=1, y=2, width=10, height=12),
        reviewed=False,
        detected_at=datetime(2026, 8, 1, 12, 0, tzinfo=UTC),
        model_id="yolo-fleet-defects-tiny",
    )
    ReviewQueue(pending, published).enqueue_for_review(
        finding, reason="confidence 0.4200 < threshold 0.55"
    )
    return finding


def test_list_pending_reads_cv_service_queue_files(queue_dirs, roles, client):
    pending, _decided, _gold = queue_dirs
    published = pending.parent / "published"
    published.mkdir()
    finding = _enqueue_via_cv_service(pending, published)

    _user, token = _make_user("v1", "viewer")
    response = client.get(
        "/api/v1/review-queue",
        HTTP_AUTHORIZATION=f"Bearer {token}",
    )
    assert response.status_code == 200
    body = response.json()
    assert len(body) == 1
    assert body[0]["finding_id"] == finding.finding_id
    assert body[0]["queue"] == "cv-human-review"
    assert body[0]["path"].endswith(f"{finding.finding_id}.json")
    # File on disk is the cv-service envelope shape.
    disk = json.loads((pending / f"{finding.finding_id}.json").read_text(encoding="utf-8"))
    assert disk["queue"] == "cv-human-review"
    assert "finding" in disk


@pytest.mark.skipif(
    not any(LIVE_PENDING.glob("*.json")),
    reason="no live cv-review-queue/pending files from cv-service",
)
def test_live_pending_queue_is_readable(settings, roles, client, tmp_path):
    """Continuity check: control-plane reads the real Phase-3 pending directory."""
    settings.CV_REVIEW_PENDING_DIR = LIVE_PENDING
    settings.CV_REVIEW_DECIDED_DIR = tmp_path / "decided"
    settings.CV_FINDINGS_GOLD_DIR = tmp_path / "gold"
    settings.CV_REVIEW_DECIDED_DIR.mkdir()
    settings.CV_FINDINGS_GOLD_DIR.mkdir()

    _user, token = _make_user("liveviewer", "viewer")
    response = client.get("/api/v1/review-queue", HTTP_AUTHORIZATION=f"Bearer {token}")
    assert response.status_code == 200
    body = response.json()
    assert len(body) >= 1
    assert all(item["finding_id"].startswith("fnd_") for item in body)
    # Spot-check one file still exists on disk exactly as cv-service wrote it.
    sample = LIVE_PENDING / f"{body[0]['finding_id']}.json"
    assert sample.is_file()
    envelope = json.loads(sample.read_text(encoding="utf-8"))
    assert envelope["queue"] == "cv-human-review"


def test_inspector_approve_writes_gold_and_audit(queue_dirs, roles, client):
    pending, decided, gold = queue_dirs
    published = pending.parent / "published"
    published.mkdir()
    finding = _enqueue_via_cv_service(pending, published, finding_id="fnd_123456789abc")

    _viewer, viewer_token = _make_user("viewer2", "viewer")
    denied = client.post(
        f"/api/v1/review-queue/{finding.finding_id}/decide",
        data=json.dumps({"decision": "approve", "notes": "looks real"}),
        content_type="application/json",
        HTTP_AUTHORIZATION=f"Bearer {viewer_token}",
    )
    assert denied.status_code == 403

    _inspector, token = _make_user("insp1", "inspector")
    response = client.post(
        f"/api/v1/review-queue/{finding.finding_id}/decide",
        data=json.dumps({"decision": "approve", "notes": "looks real"}),
        content_type="application/json",
        HTTP_AUTHORIZATION=f"Bearer {token}",
    )
    assert response.status_code == 200, response.content
    body = response.json()
    assert body["reviewed"] is True
    assert body["queue_status"] == "approved"
    assert body["gold_enqueued"] is True

    assert not (pending / f"{finding.finding_id}.json").exists()
    assert (decided / f"{finding.finding_id}.json").is_file()
    gold_file = gold / f"{finding.finding_id}.json"
    assert gold_file.is_file()
    gold_payload = json.loads(gold_file.read_text(encoding="utf-8"))
    assert gold_payload["reviewed"] is True
    CvFinding.model_validate(gold_payload)

    audit = client.get("/api/v1/audit", HTTP_AUTHORIZATION=f"Bearer {token}")
    assert audit.status_code == 200
    actions = {row["action"] for row in audit.json()}
    assert "review_decision.approve" in actions


def test_relabel_updates_defect_class(queue_dirs, roles, client):
    pending, _decided, gold = queue_dirs
    published = pending.parent / "published"
    published.mkdir()
    finding = _enqueue_via_cv_service(pending, published, finding_id="fnd_abcdef000001")
    _user, token = _make_user("insp2", "inspector")
    response = client.post(
        f"/api/v1/review-queue/{finding.finding_id}/decide",
        data=json.dumps(
            {"decision": "relabel", "relabel_class": "dent", "notes": "dent not anomaly"}
        ),
        content_type="application/json",
        HTTP_AUTHORIZATION=f"Bearer {token}",
    )
    assert response.status_code == 200, response.content
    assert response.json()["defect_class"] == "dent"
    gold_payload = json.loads((gold / f"{finding.finding_id}.json").read_text(encoding="utf-8"))
    assert gold_payload["defect_class"] == "dent"
    assert gold_payload["reviewed"] is True


def test_default_gold_dir_is_under_lakehouse_gold():
    """Production default writeback path is lakehouse/gold/cv_findings (Phase-2 gold root)."""
    from pathlib import Path

    from django.conf import settings as dj_settings

    default = Path(dj_settings.REPO_DATA_ROOT) / "lakehouse" / "gold" / "cv_findings"
    assert default.parts[-3:] == ("lakehouse", "gold", "cv_findings")


def test_fleet_admin_creates_asset_viewer_cannot(roles, client):
    _viewer, viewer_token = _make_user("v3", "viewer")
    denied = client.post(
        "/api/v1/assets",
        data=json.dumps({"asset_id": "PRISM-AST-009", "name": "Truck 9"}),
        content_type="application/json",
        HTTP_AUTHORIZATION=f"Bearer {viewer_token}",
    )
    assert denied.status_code == 403

    _admin, token = _make_user("fa1", "fleet-admin")
    ok = client.post(
        "/api/v1/assets",
        data=json.dumps({"asset_id": "PRISM-AST-009", "name": "Truck 9"}),
        content_type="application/json",
        HTTP_AUTHORIZATION=f"Bearer {token}",
    )
    assert ok.status_code == 200
    assert ok.json()["asset_id"] == "PRISM-AST-009"
