"""Pytest configuration for Django control-plane tests."""

from __future__ import annotations

import pytest
from django.contrib.auth.models import Group

pytest_plugins = ("pytest_django",)


@pytest.fixture(autouse=True)
def _ensure_q_sync(settings):
    """Unit tests run gold writeback inline (no qcluster required)."""
    if hasattr(settings, "Q_CLUSTER"):
        settings.Q_CLUSTER = {**settings.Q_CLUSTER, "sync": True}


@pytest.fixture()
def roles(db):
    for name in ("viewer", "inspector", "fleet-admin"):
        Group.objects.get_or_create(name=name)


@pytest.fixture()
def queue_dirs(tmp_path, settings):
    pending = tmp_path / "pending"
    decided = tmp_path / "decided"
    gold = tmp_path / "gold"
    pending.mkdir()
    decided.mkdir()
    gold.mkdir()
    settings.CV_REVIEW_PENDING_DIR = pending
    settings.CV_REVIEW_DECIDED_DIR = decided
    settings.CV_FINDINGS_GOLD_DIR = gold
    settings.Q_CLUSTER = {**settings.Q_CLUSTER, "sync": True}
    return pending, decided, gold
