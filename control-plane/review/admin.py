from django.contrib import admin, messages
from django.utils.html import format_html

from review.models import InspectionFinding, ReviewDecision
from review.services import apply_decision


class ReviewDecisionInline(admin.TabularInline):
    model = ReviewDecision
    extra = 0
    readonly_fields = ("decision", "relabel_class", "notes", "reviewer", "created_at")
    can_delete = False


@admin.register(InspectionFinding)
class InspectionFindingAdmin(admin.ModelAdmin):
    list_display = (
        "finding_id",
        "asset",
        "defect_class",
        "confidence",
        "queue_status",
        "reviewed",
        "detected_at",
    )
    list_filter = ("queue_status", "reviewed", "defect_class")
    search_fields = ("finding_id", "asset__asset_id", "frame_ref")
    readonly_fields = (
        "finding_id",
        "asset",
        "frame_ref",
        "confidence",
        "bounding_box",
        "model_id",
        "detected_at",
        "queue_path",
        "queue_reason",
        "payload",
        "gold_path",
        "created_at",
        "updated_at",
        "queue_file_link",
    )
    inlines = [ReviewDecisionInline]
    actions = ["approve_selected", "reject_selected"]

    @admin.display(description="Queue file")
    def queue_file_link(self, obj: InspectionFinding) -> str:
        return format_html("<code>{}</code>", obj.queue_path or "—")

    @admin.action(description="Approve selected pending findings")
    def approve_selected(self, request, queryset):
        count = 0
        for finding in queryset.filter(queue_status=InspectionFinding.QueueStatus.PENDING):
            apply_decision(
                finding_id=finding.finding_id,
                decision=ReviewDecision.Decision.APPROVE,
                reviewer=request.user,
                notes="approved via admin action",
            )
            count += 1
        self.message_user(request, f"Approved {count} finding(s).", messages.SUCCESS)

    @admin.action(description="Reject selected pending findings")
    def reject_selected(self, request, queryset):
        count = 0
        for finding in queryset.filter(queue_status=InspectionFinding.QueueStatus.PENDING):
            apply_decision(
                finding_id=finding.finding_id,
                decision=ReviewDecision.Decision.REJECT,
                reviewer=request.user,
                notes="rejected via admin action",
            )
            count += 1
        self.message_user(request, f"Rejected {count} finding(s).", messages.SUCCESS)


@admin.register(ReviewDecision)
class ReviewDecisionAdmin(admin.ModelAdmin):
    list_display = ("finding", "decision", "relabel_class", "reviewer", "created_at")
    list_filter = ("decision",)
    search_fields = ("finding__finding_id",)
