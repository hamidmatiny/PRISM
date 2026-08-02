from django.contrib import admin

from audit.models import AuditLogEntry


@admin.register(AuditLogEntry)
class AuditLogEntryAdmin(admin.ModelAdmin):
    list_display = ("created_at", "action", "object_type", "object_id", "actor_username")
    list_filter = ("action", "object_type")
    search_fields = ("object_id", "actor_username", "action")
    readonly_fields = (
        "actor",
        "actor_username",
        "action",
        "object_type",
        "object_id",
        "before",
        "after",
        "metadata",
        "created_at",
    )
