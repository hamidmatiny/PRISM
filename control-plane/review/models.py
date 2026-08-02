"""Inspection findings linked to cv-finding-schema + review decisions."""

from __future__ import annotations

from django.conf import settings
from django.db import models

from fleet.models import Asset


class InspectionFinding(models.Model):
    class QueueStatus(models.TextChoices):
        PENDING = "pending", "Pending review"
        APPROVED = "approved", "Approved"
        REJECTED = "rejected", "Rejected"
        RELABELED = "relabeled", "Relabeled"

    finding_id = models.CharField(max_length=32, unique=True, db_index=True)
    asset = models.ForeignKey(Asset, on_delete=models.CASCADE, related_name="inspection_findings")
    frame_ref = models.CharField(max_length=32)
    defect_class = models.CharField(max_length=64)
    confidence = models.FloatField()
    bounding_box = models.JSONField(null=True, blank=True)
    model_id = models.CharField(max_length=128, blank=True, default="")
    detected_at = models.DateTimeField()
    reviewed = models.BooleanField(default=False)
    queue_status = models.CharField(
        max_length=32, choices=QueueStatus.choices, default=QueueStatus.PENDING
    )
    queue_path = models.CharField(max_length=512, blank=True, default="")
    queue_reason = models.TextField(blank=True, default="")
    payload = models.JSONField(default=dict)
    gold_path = models.CharField(max_length=512, blank=True, default="")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-detected_at"]

    def __str__(self) -> str:
        return self.finding_id


class ReviewDecision(models.Model):
    class Decision(models.TextChoices):
        APPROVE = "approve", "Approve"
        REJECT = "reject", "Reject"
        RELABEL = "relabel", "Relabel"

    finding = models.ForeignKey(
        InspectionFinding, on_delete=models.CASCADE, related_name="decisions"
    )
    decision = models.CharField(max_length=16, choices=Decision.choices)
    relabel_class = models.CharField(max_length=64, blank=True, default="")
    notes = models.TextField(blank=True, default="")
    reviewer = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name="review_decisions",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self) -> str:
        return f"{self.decision}:{self.finding.finding_id}"
