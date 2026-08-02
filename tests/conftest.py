"""Pytest configuration for Django control-plane tests."""

from __future__ import annotations

import pytest

pytest_plugins = ("pytest_django",)


@pytest.fixture(autouse=True)
def _ensure_q_sync(settings):
    """Unit tests run gold writeback inline (no qcluster required)."""
    if hasattr(settings, "Q_CLUSTER"):
        settings.Q_CLUSTER = {**settings.Q_CLUSTER, "sync": True}
