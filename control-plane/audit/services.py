"""Helpers to append audit log entries."""

from __future__ import annotations

from typing import Any

from django.contrib.auth.models import AbstractBaseUser

from audit.models import AuditLogEntry


def record_audit(
    *,
    actor: AbstractBaseUser | None,
    action: str,
    object_type: str,
    object_id: str,
    before: dict[str, Any] | None = None,
    after: dict[str, Any] | None = None,
    metadata: dict[str, Any] | None = None,
) -> AuditLogEntry:
    return AuditLogEntry.objects.create(
        actor=actor if getattr(actor, "is_authenticated", False) else None,
        actor_username=getattr(actor, "username", "") or "",
        action=action,
        object_type=object_type,
        object_id=str(object_id),
        before=before,
        after=after,
        metadata=metadata or {},
    )
