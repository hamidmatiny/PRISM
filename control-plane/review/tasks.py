"""Async gold writeback for reviewed findings (Django-Q2)."""

from __future__ import annotations

import json
import logging
from pathlib import Path

from django.conf import settings

from prism_cv_finding_schema import CvFinding

logger = logging.getLogger(__name__)


def write_reviewed_finding_to_gold(finding_id: str) -> str:
    """
    Persist schema-valid CvFinding with reviewed=true into the gold findings zone.

    Path: ``$PRISM_CV_FINDINGS_GOLD_DIR/<finding_id>.json``
    (default ``.data/cv-findings/gold/``).
    """
    from review.models import InspectionFinding
    from review.queue import gold_dir

    finding = InspectionFinding.objects.get(finding_id=finding_id)
    payload = {**finding.payload, "reviewed": True, "defect_class": finding.defect_class}
    validated = CvFinding.model_validate(payload)
    out_dir = gold_dir()
    out_path = out_dir / f"{finding.finding_id}.json"
    out_path.write_text(
        json.dumps(validated.to_payload(), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    finding.gold_path = str(out_path.resolve())
    finding.save(update_fields=["gold_path", "updated_at"])
    logger.info("wrote reviewed finding to gold: %s", out_path)
    return str(out_path)


def enqueue_gold_writeback(finding_id: str) -> None:
    """
    Queue async gold writeback via Django-Q2.

    Runs inline when ``PRISM_Q_SYNC=1`` (tests) or when the DB vendor is SQLite
    (local compose fallback) to avoid multi-process SQLite lock contention.
    Postgres / RDS uses the ORM-brokered qcluster worker.
    """
    from django.db import connection

    if settings.Q_CLUSTER.get("sync") or connection.vendor == "sqlite":
        write_reviewed_finding_to_gold(finding_id)
        return
    from django_q.tasks import async_task

    async_task(
        "review.tasks.write_reviewed_finding_to_gold",
        finding_id,
        task_name=f"gold-writeback-{finding_id}",
    )


def gold_path_for(finding_id: str) -> Path:
    return Path(settings.CV_FINDINGS_GOLD_DIR) / f"{finding_id}.json"
