"""Minimal CORS middleware for the Vue cockpit (Phase 8) — no extra dependency."""

from __future__ import annotations

import os

from django.http import HttpResponse


class SimpleCorsMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response
        origins = os.environ.get(
            "PRISM_CORS_ORIGINS",
            "http://localhost:9101,http://127.0.0.1:9101",
        )
        self.allowed = {o.strip() for o in origins.split(",") if o.strip()}

    def __call__(self, request):
        origin = request.headers.get("Origin", "")
        if request.method == "OPTIONS" and origin in self.allowed:
            response = HttpResponse(status=204)
            self._apply(response, origin)
            return response
        response = self.get_response(request)
        if origin in self.allowed:
            self._apply(response, origin)
        return response

    def _apply(self, response, origin: str) -> None:
        response["Access-Control-Allow-Origin"] = origin
        response["Access-Control-Allow-Headers"] = "Authorization, Content-Type"
        response["Access-Control-Allow-Methods"] = "GET, POST, OPTIONS"
        response["Access-Control-Allow-Credentials"] = "true"
