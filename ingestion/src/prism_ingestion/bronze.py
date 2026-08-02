"""S3-shaped local bronze zone with Hive partitions ``dt=`` / ``device=``."""

from __future__ import annotations

import json
import uuid
from datetime import UTC, datetime
from pathlib import Path
from typing import Any


def hive_partition_path(
    root: Path,
    dataset: str,
    *,
    dt: str,
    device: str,
) -> Path:
    return root / dataset / f"dt={dt}" / f"device={device}"


def write_bronze_record(
    bronze_root: Path,
    dataset: str,
    record: dict[str, Any],
    *,
    device_id: str,
    event_timestamp: str | None = None,
) -> Path:
    """Write one JSON object under Hive partitions; returns the file path."""
    if event_timestamp:
        ts = datetime.fromisoformat(event_timestamp.replace("Z", "+00:00"))
    else:
        ts = datetime.now(tz=UTC)
    if ts.tzinfo is None:
        ts = ts.replace(tzinfo=UTC)
    dt = ts.astimezone(UTC).strftime("%Y-%m-%d")
    partition = hive_partition_path(bronze_root, dataset, dt=dt, device=device_id)
    partition.mkdir(parents=True, exist_ok=True)
    path = partition / f"{uuid.uuid4().hex}.json"
    path.write_text(json.dumps(record, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return path


def write_dlq_record(
    dlq_root: Path,
    record: dict[str, Any],
    *,
    reason: str,
    kind: str,
) -> Path:
    dt = datetime.now(tz=UTC).strftime("%Y-%m-%d")
    partition = dlq_root / f"dt={dt}" / f"kind={kind}"
    partition.mkdir(parents=True, exist_ok=True)
    path = partition / f"{uuid.uuid4().hex}.json"
    envelope = {
        "rejected_at": datetime.now(tz=UTC).isoformat().replace("+00:00", "Z"),
        "reason": reason,
        "kind": kind,
        "record": record,
    }
    path.write_text(json.dumps(envelope, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return path
