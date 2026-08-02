"""Human-review queue for low-confidence CV findings (Phase 5 consumer)."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from prism_cv_finding_schema import CvFinding


class ReviewQueue:
    """
    File-backed pending queue.

    Layout::

        <data_root>/cv-review-queue/pending/<finding_id>.json
        <data_root>/cv-findings/published/<finding_id>.json

    Control-plane (Phase 5) will consume the pending directory / topic.
    """

    def __init__(self, pending_dir: Path, published_dir: Path) -> None:
        self.pending_dir = pending_dir
        self.published_dir = published_dir
        self.pending_dir.mkdir(parents=True, exist_ok=True)
        self.published_dir.mkdir(parents=True, exist_ok=True)

    def enqueue_for_review(self, finding: CvFinding, *, reason: str) -> Path:
        path = self.pending_dir / f"{finding.finding_id}.json"
        envelope = {
            "queue": "cv-human-review",
            "reason": reason,
            "finding": finding.to_payload(),
        }
        path.write_text(json.dumps(envelope, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        return path

    def publish(self, finding: CvFinding) -> Path:
        path = self.published_dir / f"{finding.finding_id}.json"
        path.write_text(
            json.dumps(finding.to_payload(), indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        return path

    def list_pending(self) -> list[dict[str, Any]]:
        items: list[dict[str, Any]] = []
        for path in sorted(self.pending_dir.glob("*.json")):
            items.append(json.loads(path.read_text(encoding="utf-8")))
        return items
