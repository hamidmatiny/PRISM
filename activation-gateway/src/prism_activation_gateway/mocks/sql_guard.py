"""Tiny SQL allow-list for mock warehouses (SELECT-only, single statement)."""

from __future__ import annotations

import re

_FORBIDDEN = re.compile(
    r"\b(INSERT|UPDATE|DELETE|DROP|ALTER|CREATE|ATTACH|COPY|EXPORT|CALL|PRAGMA)\b",
    re.IGNORECASE,
)


def normalize_select(sql: str, *, default_table: str, limit: int) -> str:
    text = (sql or "").strip().rstrip(";")
    if not text:
        text = f"SELECT * FROM {default_table} ORDER BY 1 LIMIT {limit}"
    if ";" in text:
        raise ValueError("only a single SQL statement is allowed")
    if not re.match(r"(?is)^\s*SELECT\b", text):
        raise ValueError("only SELECT statements are allowed")
    if _FORBIDDEN.search(text):
        raise ValueError("statement contains a forbidden keyword")
    # Bound result size when caller omitted LIMIT.
    if not re.search(r"(?i)\bLIMIT\b", text):
        text = f"{text} LIMIT {limit}"
    return text
