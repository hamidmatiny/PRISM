"""Two-layer contract gate — accept schema-valid, contract-sane events;
reject everything else to DLQ with a stable, structured reason.

Layer 1 (structural, Pydantic): fast, cheap, catches missing/mistyped/
malformed-pattern/out-of-declared-range fields at the wire-format boundary.
Layer 2 (contract, Pandera): re-asserts a smaller, independent set of checks
against the storage/analytics contract the bronze zone relies on — catching
structurally-valid-but-implausible records Layer 1 cannot express (see
``contract_gate.py`` for the concrete null-island GPS example).

Pattern adapted from hydra-data-factory's two-pass validation
(schema_contract.py + transformer.py); PRISM's own field set and taxonomy,
not a verbatim copy of hydra's AV-specific checks.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from pydantic import ValidationError

from prism_ingestion.contract_gate import check_contract
from prism_ingestion.corruption import (
    CorruptionType,
    RejectionGate,
    classify_contract_error,
    classify_structural_error,
)
from prism_ingestion.simulator import EventKind
from prism_telemetry_schema import CameraFrameMetadata, SensorPing


@dataclass(frozen=True)
class ValidationResult:
    ok: bool
    cleaned: dict[str, Any]
    reason: str | None
    corruption_type: CorruptionType | None
    gate: RejectionGate | None

    # Backward-compatible 3-tuple unpacking: `ok, cleaned, reason = validate_event(...)`.
    def __iter__(self):
        yield self.ok
        yield self.cleaned
        yield self.reason


def validate_event(
    kind: EventKind,
    payload: dict[str, Any],
) -> ValidationResult:
    """Validate ``payload`` against the two-layer contract for ``kind``."""
    hint = payload.get("_corruption")
    working = {k: v for k, v in payload.items() if not k.startswith("_")}

    # Layer 1 — structural (Pydantic).
    try:
        if kind == "sensor_ping":
            model = SensorPing.model_validate(working)
        else:
            model = CameraFrameMetadata.model_validate(working)
    except ValidationError as exc:
        corruption_type = classify_structural_error(exc.errors(), kind=kind, hint=hint)
        return ValidationResult(
            ok=False,
            cleaned=payload,
            reason=str(exc),
            corruption_type=corruption_type,
            gate="structural",
        )

    cleaned = model.to_payload()

    # Layer 2 — contract (Pandera), independent tabular/dtype re-assertion.
    contract_ok, checks_failed, contract_reason = check_contract(kind, cleaned)
    if not contract_ok:
        corruption_type = classify_contract_error(kind=kind, checks_failed=checks_failed)
        return ValidationResult(
            ok=False,
            cleaned=payload,
            reason=contract_reason,
            corruption_type=corruption_type,
            gate="contract",
        )

    return ValidationResult(ok=True, cleaned=cleaned, reason=None, corruption_type=None, gate=None)
