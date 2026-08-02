"""Shared UTC-now helper (kept tiny and mockable for tests)."""

from __future__ import annotations

from datetime import UTC, datetime


def now_utc() -> datetime:
    return datetime.now(tz=UTC)
