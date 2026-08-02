"""
Read the file-backed CV human-review queue written by cv-service (Phase 3).

Layout (same as prism_cv_service.review_queue.ReviewQueue)::

    <data>/cv-review-queue/pending/<finding_id>.json
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from django.conf import settings

from prism_cv_finding_schema import CvFinding


def pending_dir() -> Path:
    path = Path(settings.CV_REVIEW_PENDING_DIR)
    path.mkdir(parents=True, exist_ok=True)
    return path


def decided_dir() -> Path:
    path = Path(settings.CV_REVIEW_DECIDED_DIR)
    path.mkdir(parents=True, exist_ok=True)
    return path


def gold_dir() -> Path:
    path = Path(settings.CV_FINDINGS_GOLD_DIR)
    path.mkdir(parents=True, exist_ok=True)
    return path


def list_pending_envelopes() -> list[dict[str, Any]]:
    """Load every pending JSON envelope from disk (cv-service output)."""
    items: list[dict[str, Any]] = []
    for path in sorted(pending_dir().glob("*.json")):
        envelope = json.loads(path.read_text(encoding="utf-8"))
        envelope["_path"] = str(path.resolve())
        # Validate finding payload against the shared contract.
        finding = CvFinding.model_validate(envelope["finding"])
        envelope["finding"] = finding.to_payload()
        items.append(envelope)
    return items


def load_pending_envelope(finding_id: str) -> dict[str, Any]:
    path = pending_dir() / f"{finding_id}.json"
    if not path.is_file():
        raise FileNotFoundError(f"pending finding not found: {finding_id}")
    envelope = json.loads(path.read_text(encoding="utf-8"))
    envelope["_path"] = str(path.resolve())
    envelope["finding"] = CvFinding.model_validate(envelope["finding"]).to_payload()
    return envelope


def move_to_decided(finding_id: str) -> Path:
    src = pending_dir() / f"{finding_id}.json"
    if not src.is_file():
        raise FileNotFoundError(f"pending finding not found: {finding_id}")
    dest = decided_dir() / src.name
    dest.write_text(src.read_text(encoding="utf-8"), encoding="utf-8")
    src.unlink()
    return dest
