"""Fleet domain models — Asset and WorkOrder."""

from __future__ import annotations

import secrets

from django.conf import settings
from django.db import models


class UserProfile(models.Model):
    """API bearer token for Django Ninja RBAC."""

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="profile"
    )
    api_token = models.CharField(max_length=64, unique=True, db_index=True)

    def save(self, *args, **kwargs):
        if not self.api_token:
            self.api_token = secrets.token_hex(24)
        super().save(*args, **kwargs)

    def __str__(self) -> str:
        return f"profile:{self.user.username}"


class Asset(models.Model):
    class Status(models.TextChoices):
        ACTIVE = "active", "Active"
        MAINTENANCE = "maintenance", "Maintenance"
        RETIRED = "retired", "Retired"

    asset_id = models.CharField(max_length=32, unique=True, db_index=True)
    name = models.CharField(max_length=128, blank=True, default="")
    status = models.CharField(max_length=32, choices=Status.choices, default=Status.ACTIVE)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["asset_id"]

    def __str__(self) -> str:
        return self.asset_id


class WorkOrder(models.Model):
    class Status(models.TextChoices):
        OPEN = "open", "Open"
        IN_PROGRESS = "in_progress", "In progress"
        CLOSED = "closed", "Closed"
        CANCELLED = "cancelled", "Cancelled"

    work_order_id = models.CharField(max_length=32, unique=True, db_index=True)
    asset = models.ForeignKey(Asset, on_delete=models.CASCADE, related_name="work_orders")
    title = models.CharField(max_length=200)
    description = models.TextField(blank=True, default="")
    status = models.CharField(max_length=32, choices=Status.choices, default=Status.OPEN)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name="created_work_orders",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self) -> str:
        return self.work_order_id
