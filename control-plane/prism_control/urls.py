"""URL configuration for PRISM control-plane."""

from __future__ import annotations

from django.contrib import admin
from django.http import JsonResponse
from django.urls import path
from django.views.generic.base import RedirectView

from prism_control.api import api


def health(_request):
    return JsonResponse({"status": "ok", "service": "control-plane"})


urlpatterns = [
    path("health", health, name="health"),
    path("admin/", admin.site.urls),
    # Django Ninja has no view at the bare mount path by design (only
    # /api/<endpoint> and its own /api/docs) -- redirect here so hitting
    # /api/ by hand lands on the interactive docs instead of a 404.
    path("api/", RedirectView.as_view(url="/api/docs", permanent=False)),
    path("api/", api.urls),
]
