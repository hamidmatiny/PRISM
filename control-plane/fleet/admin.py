from django.contrib import admin

from fleet.models import Asset, UserProfile, WorkOrder


@admin.register(Asset)
class AssetAdmin(admin.ModelAdmin):
    list_display = ("asset_id", "name", "status", "updated_at")
    search_fields = ("asset_id", "name")


@admin.register(WorkOrder)
class WorkOrderAdmin(admin.ModelAdmin):
    list_display = ("work_order_id", "asset", "title", "status", "created_at")
    list_filter = ("status",)
    search_fields = ("work_order_id", "title", "asset__asset_id")


@admin.register(UserProfile)
class UserProfileAdmin(admin.ModelAdmin):
    list_display = ("user", "api_token")
    search_fields = ("user__username", "api_token")
