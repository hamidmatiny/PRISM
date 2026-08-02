"""Ingestion simulator, producer, and bronze landing tests."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from prism_ingestion.bronze import hive_partition_path, write_bronze_record
from prism_ingestion.config import IngestConfig
from prism_ingestion.pipeline import IngestPipeline
from prism_ingestion.producer import FileStreamProducer, build_producer
from prism_ingestion.simulator import FleetSimulator
from prism_ingestion.validate import validate_event
from prism_telemetry_schema import CameraFrameMetadata, SensorPing


def test_simulator_emits_valid_events_when_failure_rate_zero(tmp_path: Path) -> None:
    sim = FleetSimulator(
        asset_ids=["PRISM-AST-001", "PRISM-AST-002"],
        failure_rate=0.0,
        seed=7,
        camera_ratio=0.5,
    )
    kinds = set()
    for _ in range(20):
        kind, payload = sim.generate_event()
        kinds.add(kind)
        ok, cleaned, err = validate_event(kind, payload)
        assert ok, err
        if kind == "sensor_ping":
            SensorPing.model_validate(cleaned)
        else:
            CameraFrameMetadata.model_validate(cleaned)
    assert kinds == {"sensor_ping", "camera_frame"}


def test_simulator_corruption_is_rejected_by_contract() -> None:
    sim = FleetSimulator(asset_ids=["PRISM-AST-001"], failure_rate=1.0, seed=1)
    rejected = 0
    for _ in range(12):
        kind, payload = sim.generate_event()
        ok, _, _ = validate_event(kind, payload)
        if not ok:
            rejected += 1
            cleaned = {k: v for k, v in payload.items() if k != "_corruption"}
            with pytest.raises(ValidationError):
                if kind == "sensor_ping":
                    SensorPing.model_validate(cleaned)
                else:
                    CameraFrameMetadata.model_validate(cleaned)
    assert rejected == 12


def test_file_producer_writes_ndjson(tmp_path: Path) -> None:
    producer = FileStreamProducer(tmp_path / "stream", stream_name="prism-fleet-events")
    producer.ensure_stream()
    record_id = producer.put_record(
        partition_key="PRISM-AST-001",
        data={"event_type": "sensor_ping", "asset_id": "PRISM-AST-001"},
    )
    shard = tmp_path / "stream" / "shard-000000"
    files = list(shard.glob("records-*.ndjson"))
    assert len(files) == 1
    line = files[0].read_text(encoding="utf-8").strip()
    envelope = json.loads(line)
    assert envelope["record_id"] == record_id
    assert envelope["partition_key"] == "PRISM-AST-001"


def test_bronze_hive_partition_layout(tmp_path: Path) -> None:
    path = write_bronze_record(
        tmp_path / "bronze",
        "sensor_pings",
        {"asset_id": "PRISM-AST-001", "device_id": "PRISM-DEV-001"},
        device_id="PRISM-DEV-001",
        event_timestamp="2026-08-01T12:00:00Z",
    )
    assert "dt=2026-08-01" in path.parts
    assert "device=PRISM-DEV-001" in path.parts
    expected = hive_partition_path(
        tmp_path / "bronze",
        "sensor_pings",
        dt="2026-08-01",
        device="PRISM-DEV-001",
    )
    assert path.parent == expected


def test_pipeline_lands_validated_records_and_dlq(tmp_path: Path) -> None:
    config = IngestConfig(
        backend="file",
        data_root=tmp_path,
        emit_rate_hz=100.0,
        failure_rate=0.5,
        duration_seconds=0.0,
        asset_ids=("PRISM-AST-001",),
        seed=99,
        health_port=0,
    )
    pipeline = IngestPipeline.from_config(config)
    for _ in range(40):
        pipeline.process_one()

    assert pipeline.stats.emitted == 40
    assert pipeline.stats.accepted + pipeline.stats.rejected == 40
    assert pipeline.stats.accepted > 0
    assert pipeline.stats.rejected > 0

    bronze_files = list((tmp_path / "bronze").rglob("*.json"))
    # DLQ + accepted bronze
    assert any("sensor_pings" in p.parts or "camera_frames" in p.parts for p in bronze_files)
    assert any("_dlq" in p.parts for p in bronze_files)
    assert list((tmp_path / "kinesis" / "streams" / "prism-fleet-events").rglob("*.ndjson"))


def test_build_producer_rejects_unknown_backend(tmp_path: Path) -> None:
    try:
        build_producer(
            "aws",
            stream_name="x",
            file_root=tmp_path,
            localstack_endpoint="http://localhost:4566",
            aws_region="us-east-1",
        )
        raise AssertionError("expected ValueError")
    except ValueError as exc:
        assert "Unknown PRISM_INGEST_BACKEND" in str(exc)
