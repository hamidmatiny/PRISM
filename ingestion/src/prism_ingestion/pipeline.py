"""Generate → validate → stream → bronze (or DLQ)."""

from __future__ import annotations

import logging
import re
import time
from contextlib import nullcontext
from dataclasses import dataclass, field
from typing import Any

from prism_ingestion.bronze import write_bronze_record, write_dlq_record
from prism_ingestion.config import IngestConfig
from prism_ingestion.incident_client import report_observation
from prism_ingestion.producer import StreamProducer, build_producer
from prism_ingestion.simulator import FleetSimulator
from prism_ingestion.sources import EventSource, LiveEventSource, ScenarioClient
from prism_ingestion.validate import validate_event
from prism_telemetry_schema import ASSET_ID_PATTERN

logger = logging.getLogger(__name__)

_ASSET_ID_RE = re.compile(ASSET_ID_PATTERN)


def _known_asset_id(raw: Any) -> str | None:
    """Only hand incident-engine an asset_id that actually looks like a real
    fleet asset. On rejection, ``result.cleaned`` is the *raw, unvalidated*
    payload -- if the corruption that caused the rejection was itself in
    asset_id (scenario-engine's ``bad_id_pattern`` strategy, e.g.
    ``BAD-PRISM-AST-002``), reporting that raw string creates a permanent
    phantom breaker entry for an asset that never existed and never will
    send a legitimate observation to heal it. Pre-existing since Phase 14's
    incident-engine wiring -- Phase 15's Breaker Board was just the first
    thing to make it visible.
    """
    if not isinstance(raw, str):
        return None
    return raw if _ASSET_ID_RE.fullmatch(raw) else None


@dataclass
class PipelineStats:
    emitted: int = 0
    accepted: int = 0
    rejected: int = 0
    skipped: int = 0
    sensor_pings: int = 0
    camera_frames: int = 0
    last_error: str | None = None
    running: bool = False
    by_corruption_type: dict[str, int] = field(default_factory=dict)

    def as_dict(self) -> dict[str, Any]:
        return {
            "emitted": self.emitted,
            "accepted": self.accepted,
            "rejected": self.rejected,
            "skipped": self.skipped,
            "sensor_pings": self.sensor_pings,
            "camera_frames": self.camera_frames,
            "last_error": self.last_error,
            "running": self.running,
            "by_corruption_type": dict(self.by_corruption_type),
        }


@dataclass
class IngestPipeline:
    config: IngestConfig
    source: EventSource
    producer: StreamProducer
    stats: PipelineStats = field(default_factory=PipelineStats)
    _stop: bool = False
    # Retained for tests that still construct with simulator=
    simulator: FleetSimulator | None = None

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
        source: EventSource
        simulator: FleetSimulator | None = None
        mode = config.source_mode.strip().lower()
        if mode == "scenario":
            source = ScenarioClient(config.scenario_url)
        elif mode == "live":
            simulator = FleetSimulator(
                asset_ids=config.asset_ids,
                failure_rate=config.failure_rate,
                seed=config.seed,
            )
            source = LiveEventSource(simulator)
        else:
            raise ValueError(f"unsupported PRISM_SOURCE_MODE={config.source_mode!r}")
        return cls(config=config, source=source, producer=producer, simulator=simulator)

    def stop(self) -> None:
        self._stop = True

    def process_one(self) -> bool:
        """Process a single event. Returns True if accepted to bronze."""
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
            generated = self.source.generate_event()
            if generated is None:
                self.stats.skipped += 1
                if span is not None:
                    span.set_attribute("prism.skipped", True)
                return False

            kind, payload = generated
            self.stats.emitted += 1
            if kind == "sensor_ping":
                self.stats.sensor_pings += 1
                dataset = "sensor_pings"
            else:
                self.stats.camera_frames += 1
                dataset = "camera_frames"
            if span is not None:
                span.set_attribute("prism.event_kind", kind)
                span.set_attribute("prism.source_mode", self.config.source_mode)

            result = validate_event(kind, payload)
            if not result.ok:
                self.stats.rejected += 1
                self.stats.last_error = result.reason
                corruption_type = result.corruption_type or "schema_validation"
                self.stats.by_corruption_type[corruption_type] = (
                    self.stats.by_corruption_type.get(corruption_type, 0) + 1
                )
                write_dlq_record(
                    self.config.dlq_root,
                    payload,
                    reason=result.reason or "validation_failed",
                    kind=kind,
                    corruption_type=result.corruption_type,
                    gate=result.gate,
                )
                report_observation(
                    self.config.incident_engine_url,
                    asset_id=_known_asset_id(
                        result.cleaned.get("asset_id") if isinstance(result.cleaned, dict) else None
                    ),
                    kind="ingestion_quarantined",
                )
                if span is not None:
                    span.set_attribute("prism.accepted", False)
                    span.set_attribute("prism.corruption_type", corruption_type)
                    span.set_attribute("prism.rejection_gate", result.gate or "unknown")
                return False

            cleaned = result.cleaned
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
            report_observation(
                self.config.incident_engine_url,
                asset_id=partition_key if partition_key != "unknown" else None,
                kind="ingestion_accepted",
            )
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
            "Ingestion pipeline starting backend=%s source_mode=%s rate=%.2fHz",
            self.config.backend,
            self.config.source_mode,
            self.config.emit_rate_hz,
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
