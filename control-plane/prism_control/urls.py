"""URL configuration for PRISM control-plane."""

from __future__ import annotations

from django.contrib import admin
from django.http import JsonResponse
from django.urls import path

from prism_control.api import api


def health(_request):
    return JsonResponse({"status": "ok", "service": "control-plane"})


urlpatterns = [
    path("health", health, name="health"),
    path("admin/", admin.site.urls),
    path("api/", api.urls),
]
