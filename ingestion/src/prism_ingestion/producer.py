"""Kinesis producer with file-based fallback (and optional LocalStack)."""

from __future__ import annotations

import json
import logging
import uuid
from abc import ABC, abstractmethod
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


class StreamProducer(ABC):
    @abstractmethod
    def put_record(self, *, partition_key: str, data: dict[str, Any]) -> str:
        """Publish one record; return a producer-specific sequence / record id."""

    @abstractmethod
    def ensure_stream(self) -> None:
        """Create the stream if needed (no-op for file backend)."""


class FileStreamProducer(StreamProducer):
    """
    Local Kinesis-shaped fallback: NDJSON shards under a stream directory.

    Layout::

        <root>/shard-000000/records-<ts>-<id>.ndjson
    """

    def __init__(self, stream_root: Path, *, stream_name: str) -> None:
        self.stream_root = stream_root
        self.stream_name = stream_name
        self._shard_dir = stream_root / "shard-000000"

    def ensure_stream(self) -> None:
        self._shard_dir.mkdir(parents=True, exist_ok=True)
        meta = self.stream_root / "stream.json"
        if not meta.exists():
            meta.write_text(
                json.dumps(
                    {
                        "stream_name": self.stream_name,
                        "backend": "file",
                        "shard_count": 1,
                    },
                    indent=2,
                )
                + "\n",
                encoding="utf-8",
            )

    def put_record(self, *, partition_key: str, data: dict[str, Any]) -> str:
        self.ensure_stream()
        record_id = uuid.uuid4().hex
        arrival = datetime.now(tz=UTC).isoformat().replace("+00:00", "Z")
        envelope = {
            "record_id": record_id,
            "partition_key": partition_key,
            "approximate_arrival_timestamp": arrival,
            "data": data,
        }
        path = self._shard_dir / f"records-{arrival.replace(':', '')}-{record_id}.ndjson"
        with path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(envelope, separators=(",", ":")) + "\n")
        return record_id


class LocalstackKinesisProducer(StreamProducer):
    """Kinesis put_record against LocalStack. Never targets real AWS by default."""

    def __init__(
        self,
        *,
        stream_name: str,
        endpoint_url: str,
        region_name: str = "us-east-1",
    ) -> None:
        try:
            import boto3
        except ImportError as exc:  # pragma: no cover
            raise RuntimeError(
                "boto3 is required for PRISM_INGEST_BACKEND=localstack "
                "(pip install 'prism-ingestion[localstack]')"
            ) from exc

        if not endpoint_url:
            raise ValueError("LocalStack endpoint_url is required")
        # Refuse accidental real-AWS calls without an explicit endpoint.
        if "amazonaws.com" in endpoint_url:
            raise ValueError("Refusing amazonaws.com endpoint (ADR-001)")

        self.stream_name = stream_name
        self._client = boto3.client(
            "kinesis",
            endpoint_url=endpoint_url,
            region_name=region_name,
            aws_access_key_id="test",
            aws_secret_access_key="test",
        )

    def ensure_stream(self) -> None:
        existing = self._client.list_streams().get("StreamNames", [])
        if self.stream_name in existing:
            return
        self._client.create_stream(StreamName=self.stream_name, ShardCount=1)
        waiter = self._client.get_waiter("stream_exists")
        waiter.wait(StreamName=self.stream_name)
        logger.info("Created LocalStack stream %s", self.stream_name)

    def put_record(self, *, partition_key: str, data: dict[str, Any]) -> str:
        self.ensure_stream()
        response = self._client.put_record(
            StreamName=self.stream_name,
            Data=json.dumps(data, separators=(",", ":")).encode("utf-8"),
            PartitionKey=partition_key,
        )
        return str(response.get("SequenceNumber", ""))


def build_producer(
    backend: str,
    *,
    stream_name: str,
    file_root: Path,
    localstack_endpoint: str,
    aws_region: str,
) -> StreamProducer:
    if backend == "file":
        return FileStreamProducer(file_root, stream_name=stream_name)
    if backend == "localstack":
        return LocalstackKinesisProducer(
            stream_name=stream_name,
            endpoint_url=localstack_endpoint,
            region_name=aws_region,
        )
    raise ValueError(f"Unknown PRISM_INGEST_BACKEND={backend!r} (expected file|localstack)")
