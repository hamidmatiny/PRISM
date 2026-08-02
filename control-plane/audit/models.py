"""Immutable audit trail for state-changing actions."""

from __future__ import annotations

from django.conf import settings
from django.db import models


class AuditLogEntry(models.Model):
    actor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="audit_entries",
    )
    actor_username = models.CharField(max_length=150, blank=True, default="")
    action = models.CharField(max_length=64, db_index=True)
    object_type = models.CharField(max_length=64, db_index=True)
    object_id = models.CharField(max_length=128, db_index=True)
    before = models.JSONField(null=True, blank=True)
    after = models.JSONField(null=True, blank=True)
    metadata = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        ordering = ["-created_at"]
        verbose_name_plural = "audit log entries"

    def __str__(self) -> str:
        return f"{self.action}:{self.object_type}:{self.object_id}"
