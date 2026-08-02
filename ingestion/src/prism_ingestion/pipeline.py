"""Generate → validate → stream → bronze (or DLQ)."""

from __future__ import annotations

import logging
import time
from contextlib import nullcontext
from dataclasses import dataclass, field
from typing import Any

from prism_ingestion.bronze import write_bronze_record, write_dlq_record
from prism_ingestion.config import IngestConfig
from prism_ingestion.producer import StreamProducer, build_producer
from prism_ingestion.simulator import FleetSimulator
from prism_ingestion.validate import validate_event

logger = logging.getLogger(__name__)


@dataclass
class PipelineStats:
    emitted: int = 0
    accepted: int = 0
    rejected: int = 0
    sensor_pings: int = 0
    camera_frames: int = 0
    last_error: str | None = None
    running: bool = False

    def as_dict(self) -> dict[str, Any]:
        return {
            "emitted": self.emitted,
            "accepted": self.accepted,
            "rejected": self.rejected,
            "sensor_pings": self.sensor_pings,
            "camera_frames": self.camera_frames,
            "last_error": self.last_error,
            "running": self.running,
        }


@dataclass
class IngestPipeline:
    config: IngestConfig
    simulator: FleetSimulator
    producer: StreamProducer
    stats: PipelineStats = field(default_factory=PipelineStats)
    _stop: bool = False

    @classmethod
    def from_config(cls, config: IngestConfig) -> IngestPipeline:
        producer = build_producer(
            config.backend,
            stream_name=config.stream_name,
            file_root=config.kinesis_file_root,
            localstack_endpoint=config.localstack_endpoint,
            aws_region=config.aws_region,
        )
        producer.ensure_stream()
        simulator = FleetSimulator(
            asset_ids=config.asset_ids,
            failure_rate=config.failure_rate,
            seed=config.seed,
        )
        return cls(config=config, simulator=simulator, producer=producer)

    def stop(self) -> None:
        self._stop = True

    def process_one(self) -> bool:
        """Process a single simulated event. Returns True if accepted to bronze."""
        try:
            from prism_otel import get_tracer

            tracer = get_tracer("prism.ingestion")
        except ImportError:
            tracer = None

        span_cm = (
            tracer.start_as_current_span("ingest.process_one")
            if tracer is not None
            else nullcontext()
        )
        with span_cm as span:
            kind, payload = self.simulator.generate_event()
            self.stats.emitted += 1
            if kind == "sensor_ping":
                self.stats.sensor_pings += 1
                dataset = "sensor_pings"
            else:
                self.stats.camera_frames += 1
                dataset = "camera_frames"
            if span is not None:
                span.set_attribute("prism.event_kind", kind)

            ok, cleaned, error = validate_event(kind, payload)
            if not ok:
                self.stats.rejected += 1
                self.stats.last_error = error
                write_dlq_record(
                    self.config.dlq_root,
                    payload,
                    reason=error or "validation_failed",
                    kind=kind,
                )
                if span is not None:
                    span.set_attribute("prism.accepted", False)
                return False

            partition_key = str(cleaned.get("asset_id", "unknown"))
            self.producer.put_record(partition_key=partition_key, data=cleaned)
            device_id = str(cleaned.get("device_id", "unknown"))
            write_bronze_record(
                self.config.bronze_root,
                dataset,
                cleaned,
                device_id=device_id,
                event_timestamp=str(cleaned.get("timestamp")),
            )
            self.stats.accepted += 1
            if span is not None:
                span.set_attribute("prism.accepted", True)
                span.set_attribute("prism.asset_id", partition_key)
            return True

    def run(self) -> PipelineStats:
        if self.config.emit_rate_hz <= 0:
            raise ValueError("emit_rate_hz must be positive")
        interval = 1.0 / self.config.emit_rate_hz
        deadline = None
        if self.config.duration_seconds > 0:
            deadline = time.monotonic() + self.config.duration_seconds

        self.stats.running = True
        logger.info(
            "Ingestion pipeline starting backend=%s rate=%.2fHz failure_rate=%.2f",
            self.config.backend,
            self.config.emit_rate_hz,
            self.config.failure_rate,
        )
        try:
            while not self._stop:
                if deadline is not None and time.monotonic() >= deadline:
                    break
                loop_start = time.monotonic()
                self.process_one()
                sleep_for = interval - (time.monotonic() - loop_start)
                if sleep_for > 0:
                    time.sleep(sleep_for)
        finally:
            self.stats.running = False
            logger.info("Ingestion pipeline stopped stats=%s", self.stats.as_dict())
        return self.stats
