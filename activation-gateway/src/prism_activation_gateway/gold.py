"""Resolve local / file:// / s3:// gold table URIs for mock warehouses."""

from __future__ import annotations

from pathlib import Path
from urllib.parse import unquote, urlparse


def gold_uri_to_path(gold_uri: str) -> Path:
    """Map a gold URI to a local filesystem path (mock / local-dev only)."""
    parsed = urlparse(gold_uri)
    if parsed.scheme in {"", "file"}:
        path = Path(unquote(parsed.path if parsed.scheme == "file" else gold_uri))
        return path
    if parsed.scheme == "s3":
        # Local mock maps s3://bucket/key → $PRISM_DATA_ROOT/<key> when present,
        # otherwise treat the path component as a relative lakehouse key.
        key = unquote(parsed.path).lstrip("/")
        # Common layout: s3://prism-gold/gold/<table>
        candidates = [
            Path(".data") / key,
            Path(".data/lakehouse") / key,
            Path(key),
        ]
        for candidate in candidates:
            if candidate.exists():
                return candidate.resolve()
        raise FileNotFoundError(f"s3 gold URI {gold_uri!r} has no local mock mapping under .data/")
    raise ValueError(f"unsupported gold URI scheme: {parsed.scheme!r}")


def assert_gold_readable(gold_uri: str) -> Path:
    path = gold_uri_to_path(gold_uri)
    if not path.exists():
        raise FileNotFoundError(f"gold path does not exist: {path}")
    parquet = list(path.glob("**/*.parquet"))
    if not parquet:
        raise FileNotFoundError(f"no parquet files under gold path: {path}")
    return path
