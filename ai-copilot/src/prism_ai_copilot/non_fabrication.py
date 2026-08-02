"""Evidence bag + non-fabrication checks (ADR-004 — Vulcan ADR-014 pattern)."""

from __future__ import annotations

import re
from collections.abc import Iterable
from dataclasses import asdict, dataclass
from typing import Any

_NUM_RE = re.compile(
    r"""
    (?<![A-Za-z0-9_./-])
    [+-]?
    (?:
        \d+\.\d+(?:[eE][+-]?\d+)?
      | \d+(?:[eE][+-]?\d+)
      | \d+\.\d+
      | \d+
    )
    (?![A-Za-z0-9_])
    """,
    re.VERBOSE,
)

# Identifiers that count as factual claims in answers (must be in evidence).
_ID_RE = re.compile(
    r"\b("
    r"PRISM-AST-\d+"
    r"|fnd_[0-9a-f]+"
    r"|wo_[0-9a-f]+"
    r"|redshift|snowflake|asset_daily_metrics"
    r"|dent|crack|tire_wear|sensor_obstruction|anomaly"
    r"|in_progress"  # multi-token status; bare words like open/pending are too common in prose
    r")\b",
    re.IGNORECASE,
)


@dataclass(frozen=True)
class EvidenceItem:
    tool: str
    kind: str  # "number" | "id" | "string"
    key: str
    value: Any
    value_str: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def format_number(value: float | int) -> str:
    f = float(value)
    if f == int(f) and abs(f) < 1e15:
        return str(int(f))
    return f"{f:.12g}"


def add_number(evidence: list[EvidenceItem], tool: str, key: str, value: float | int) -> str:
    s = format_number(value)
    evidence.append(
        EvidenceItem(tool=tool, kind="number", key=key, value=float(value), value_str=s)
    )
    return s


def add_id(evidence: list[EvidenceItem], tool: str, key: str, value: str) -> str:
    s = str(value).strip()
    evidence.append(EvidenceItem(tool=tool, kind="id", key=key, value=s, value_str=s))
    return s


def add_string(evidence: list[EvidenceItem], tool: str, key: str, value: str) -> str:
    s = str(value)
    evidence.append(EvidenceItem(tool=tool, kind="string", key=key, value=s, value_str=s))
    return s


def extract_numbers(text: str) -> list[str]:
    return [m.group(0) for m in _NUM_RE.finditer(text)]


def extract_claim_ids(text: str) -> list[str]:
    return [m.group(0) for m in _ID_RE.finditer(text)]


def _number_allowed(token: str, allowed: Iterable[str], allowed_floats: Iterable[float]) -> bool:
    if token in allowed:
        return True
    try:
        tv = float(token)
    except ValueError:
        return False
    for af in allowed_floats:
        if abs(tv - af) <= max(1e-12, abs(af) * 1e-9):
            return True
    return False


def assert_answer_grounded(answer: str, evidence: list[EvidenceItem]) -> None:
    """Fail if any number or known id in ``answer`` is not in tool evidence."""
    allowed_num_strs = {e.value_str for e in evidence if e.kind == "number"}
    allowed_floats = [float(e.value) for e in evidence if e.kind == "number"]
    allowed_ids = {e.value_str.lower() for e in evidence if e.kind == "id"}

    for token in extract_numbers(answer):
        if not _number_allowed(token, allowed_num_strs, allowed_floats):
            raise AssertionError(
                f"non-fabrication FAIL: number {token!r} in answer is not in tool evidence "
                f"(allowed={sorted(allowed_num_strs)})"
            )

    for claim_id in extract_claim_ids(answer):
        if claim_id.lower() not in allowed_ids:
            raise AssertionError(
                f"non-fabrication FAIL: id {claim_id!r} in answer is not in tool evidence "
                f"(allowed={sorted(allowed_ids)})"
            )
