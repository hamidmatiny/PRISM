"""Runtime configuration for the ingestion service (env-driven, local-first)."""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path


def _float_env(name: str, default: float) -> float:
    raw = os.getenv(name)
    if raw is None or raw == "":
        return default
    return float(raw)


def _int_env(name: str, default: int) -> int:
    raw = os.getenv(name)
    if raw is None or raw == "":
        return default
    return int(raw)


@dataclass(frozen=True)
class IngestConfig:
    """Ingestion settings. Defaults require zero cloud credentials (ADR-001)."""

    backend: str = "file"  # file | localstack
    source_mode: str = "live"  # live | scenario
    scenario_url: str = "http://127.0.0.1:9107"
    data_root: Path = Path(".data")
    stream_name: str = "prism-fleet-events"
    emit_rate_hz: float = 2.0
    failure_rate: float = 0.05
    duration_seconds: float = 0.0  # 0 = run until stopped
    asset_ids: tuple[str, ...] = ("PRISM-AST-001", "PRISM-AST-002", "PRISM-AST-003")
    seed: int | None = 42
    health_host: str = "0.0.0.0"
    health_port: int = 9105
    localstack_endpoint: str = "http://localhost:4566"
    aws_region: str = "us-east-1"
    extra_env: dict[str, str] = field(default_factory=dict)

    @property
    def bronze_root(self) -> Path:
        return self.data_root / "bronze"

    @property
    def kinesis_file_root(self) -> Path:
        return self.data_root / "kinesis" / "streams" / self.stream_name

    @property
    def dlq_root(self) -> Path:
        return self.bronze_root / "_dlq"

    @classmethod
    def from_env(cls) -> IngestConfig:
        assets_raw = os.getenv("PRISM_ASSET_IDS", "PRISM-AST-001,PRISM-AST-002,PRISM-AST-003")
        asset_ids = tuple(a.strip() for a in assets_raw.split(",") if a.strip())
        seed_raw = os.getenv("PRISM_SIM_SEED", "42")
        seed = None if seed_raw.lower() in {"", "none", "null"} else int(seed_raw)
        return cls(
            backend=os.getenv("PRISM_INGEST_BACKEND", "file").strip().lower(),
            source_mode=os.getenv("PRISM_SOURCE_MODE", "live").strip().lower(),
            scenario_url=os.getenv("PRISM_SCENARIO_URL", "http://127.0.0.1:9107").strip(),
            data_root=Path(os.getenv("PRISM_DATA_ROOT", ".data")),
            stream_name=os.getenv("PRISM_KINESIS_STREAM", "prism-fleet-events"),
            emit_rate_hz=_float_env("PRISM_EMIT_RATE", 2.0),
            failure_rate=_float_env("PRISM_FAILURE_RATE", 0.05),
            duration_seconds=_float_env("PRISM_DURATION_SECONDS", 0.0),
            asset_ids=asset_ids or ("PRISM-AST-001",),
            seed=seed,
            health_host=os.getenv("PRISM_HEALTH_HOST", "0.0.0.0"),
            health_port=_int_env("PRISM_INGESTION_PORT", 9105),
            localstack_endpoint=os.getenv("LOCALSTACK_ENDPOINT", "http://localhost:4566"),
            aws_region=os.getenv("AWS_DEFAULT_REGION", "us-east-1"),
        )
