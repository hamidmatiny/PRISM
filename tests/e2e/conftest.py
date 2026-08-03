"""E2E fixtures — live compose stack (ADR-001: local emulators only)."""

from __future__ import annotations

import os
import urllib.error
import urllib.request

import pytest


def _healthy(url: str) -> bool:
    try:
        with urllib.request.urlopen(url, timeout=3) as resp:
            return 200 <= (resp.getcode() or 0) < 300
    except (urllib.error.URLError, TimeoutError, OSError):
        return False


def pytest_configure(config: pytest.Config) -> None:
    config.addinivalue_line(
        "markers",
        "e2e: live docker-compose golden-path tests (set PRISM_E2E=1)",
    )


@pytest.fixture(scope="session")
def e2e_enabled() -> bool:
    return os.environ.get("PRISM_E2E", "").lower() in {"1", "true", "yes"}


@pytest.fixture(scope="session")
def stack_urls(e2e_enabled: bool) -> dict[str, str]:
    if not e2e_enabled:
        pytest.skip("PRISM_E2E not set — live golden-path skipped (unit CI)")
    urls = {
        "ingestion": os.environ.get("PRISM_INGESTION_URL", "http://127.0.0.1:9105"),
        "cv": os.environ.get("PRISM_CV_URL", "http://127.0.0.1:9102"),
        "activation": os.environ.get("PRISM_ACTIVATION_URL", "http://127.0.0.1:9103"),
        "control": os.environ.get("PRISM_CONTROL_PLANE_URL", "http://127.0.0.1:9100"),
        "copilot": os.environ.get("PRISM_COPILOT_URL", "http://127.0.0.1:9104"),
        "cockpit": os.environ.get("PRISM_COCKPIT_URL", "http://127.0.0.1:9101"),
        # Phase 19 — chaos golden path needs these directly plus via the cockpit proxy.
        "incident": os.environ.get("PRISM_INCIDENT_ENGINE_URL", "http://127.0.0.1:9108"),
        "scenario": os.environ.get("PRISM_SCENARIO_URL", "http://127.0.0.1:9107"),
    }
    missing: list[str] = []
    for name, base in urls.items():
        probe = f"{base}/" if name == "cockpit" else f"{base}/health"
        if not _healthy(probe):
            missing.append(name)
    if missing:
        pytest.skip(f"live stack not healthy: {missing} — run make demo first")
    return urls
