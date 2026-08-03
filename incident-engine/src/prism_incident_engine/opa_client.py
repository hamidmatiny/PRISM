"""OPA policy evaluation for trip + escalation decisions (Phase 18 / ADR-001).

Two local modes (never a paid SaaS):

1. HTTP — ``PRISM_OPA_URL`` points at ``opa run --server`` (Compose service).
2. CLI eval — ``opa eval`` against ``PRISM_OPA_POLICY_DIR`` (unit tests / no sidecar).

When neither works, trip evaluation **fails open** (does not invent a trip) and
``ready`` stays false so ``/health`` cannot claim policy_engine readiness
(ADR-005). We deliberately do **not** silently fall back to the old YAML
threshold comparisons in ``fsm.py``.
"""

from __future__ import annotations

import json
import logging
import os
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import httpx

log = logging.getLogger(__name__)

# Packaged next to the Python package: incident-engine/policies/rego
_DEFAULT_POLICY_DIR = Path(__file__).resolve().parents[2] / "policies" / "rego"


@dataclass(frozen=True)
class TripDecision:
    trip: bool
    reason: str | None
    ready: bool
    error: str | None = None
    mode: str = "unavailable"


@dataclass(frozen=True)
class EscalationRoute:
    channel: str
    severity: str
    notify: list[str]
    policy: str
    ready: bool
    error: str | None = None


class PolicyEngine:
    """Evaluate Rego trip + escalation policies."""

    def evaluate_trip(self, input_doc: dict[str, Any]) -> TripDecision:
        raise NotImplementedError

    def evaluate_escalation(self, reason: str) -> EscalationRoute:
        raise NotImplementedError

    def ready(self) -> bool:
        raise NotImplementedError

    @property
    def mode(self) -> str:
        raise NotImplementedError

    @property
    def policy_dir(self) -> str:
        raise NotImplementedError


class UnavailablePolicyEngine(PolicyEngine):
    def evaluate_trip(self, input_doc: dict[str, Any]) -> TripDecision:
        return TripDecision(
            trip=False,
            reason=None,
            ready=False,
            error="policy_engine_unavailable",
            mode="unavailable",
        )

    def evaluate_escalation(self, reason: str) -> EscalationRoute:
        return EscalationRoute(
            channel="mock_webhook",
            severity="info",
            notify=["ops"],
            policy="unknown",
            ready=False,
            error="policy_engine_unavailable",
        )

    def ready(self) -> bool:
        return False

    @property
    def mode(self) -> str:
        return "unavailable"

    @property
    def policy_dir(self) -> str:
        return ""


class HttpPolicyEngine(PolicyEngine):
    def __init__(self, base_url: str, policy_dir: Path, *, timeout_s: float = 2.0) -> None:
        self._base = base_url.rstrip("/")
        self._policy_dir = policy_dir
        self._timeout = timeout_s

    def evaluate_trip(self, input_doc: dict[str, Any]) -> TripDecision:
        try:
            with httpx.Client(timeout=self._timeout) as client:
                resp = client.post(
                    f"{self._base}/v1/data/prism/trip/decision",
                    json={"input": input_doc},
                )
                resp.raise_for_status()
                result = resp.json().get("result") or {}
        except Exception as exc:  # noqa: BLE001 — honest fail-open
            log.warning("OPA HTTP trip eval failed: %s", exc)
            return TripDecision(
                trip=False,
                reason=None,
                ready=False,
                error=str(exc),
                mode="http",
            )
        return TripDecision(
            trip=bool(result.get("trip")),
            reason=result.get("reason"),
            ready=True,
            mode="http",
        )

    def evaluate_escalation(self, reason: str) -> EscalationRoute:
        try:
            with httpx.Client(timeout=self._timeout) as client:
                resp = client.post(
                    f"{self._base}/v1/data/prism/escalation/route",
                    json={"input": {"reason": reason}},
                )
                resp.raise_for_status()
                result = resp.json().get("result") or {}
        except Exception as exc:  # noqa: BLE001
            log.warning("OPA HTTP escalation eval failed: %s", exc)
            return EscalationRoute(
                channel="mock_webhook",
                severity="info",
                notify=["ops"],
                policy="unknown",
                ready=False,
                error=str(exc),
            )
        return EscalationRoute(
            channel=str(result.get("channel", "mock_webhook")),
            severity=str(result.get("severity", "info")),
            notify=[str(x) for x in (result.get("notify") or ["ops"])],
            policy=str(result.get("policy", "unknown")),
            ready=True,
        )

    def ready(self) -> bool:
        try:
            with httpx.Client(timeout=self._timeout) as client:
                resp = client.get(f"{self._base}/health")
                return resp.status_code == 200
        except Exception:  # noqa: BLE001
            return False

    @property
    def mode(self) -> str:
        return "http"

    @property
    def policy_dir(self) -> str:
        return str(self._policy_dir)


class EvalPolicyEngine(PolicyEngine):
    """Local ``opa eval`` against a policy directory (no long-lived server)."""

    def __init__(self, opa_bin: str, policy_dir: Path) -> None:
        self._opa = opa_bin
        self._policy_dir = policy_dir

    def _eval(self, query: str, input_doc: dict[str, Any]) -> Any:
        proc = subprocess.run(
            [
                self._opa,
                "eval",
                "-f",
                "values",
                "-d",
                str(self._policy_dir),
                "-I",
                query,
            ],
            input=json.dumps(input_doc),
            capture_output=True,
            text=True,
            timeout=10,
            check=False,
        )
        if proc.returncode != 0:
            raise RuntimeError(proc.stderr.strip() or f"opa eval exit {proc.returncode}")
        # `-f values` prints a JSON array of expression values (may be multi-line).
        payload = json.loads(proc.stdout or "null")
        if isinstance(payload, list):
            return payload[0] if payload else None
        return payload

    def evaluate_trip(self, input_doc: dict[str, Any]) -> TripDecision:
        try:
            result = self._eval("data.prism.trip.decision", input_doc) or {}
        except Exception as exc:  # noqa: BLE001
            log.warning("OPA eval trip failed: %s", exc)
            return TripDecision(
                trip=False,
                reason=None,
                ready=False,
                error=str(exc),
                mode="eval",
            )
        return TripDecision(
            trip=bool(result.get("trip")),
            reason=result.get("reason"),
            ready=True,
            mode="eval",
        )

    def evaluate_escalation(self, reason: str) -> EscalationRoute:
        try:
            result = self._eval("data.prism.escalation.route", {"reason": reason}) or {}
        except Exception as exc:  # noqa: BLE001
            log.warning("OPA eval escalation failed: %s", exc)
            return EscalationRoute(
                channel="mock_webhook",
                severity="info",
                notify=["ops"],
                policy="unknown",
                ready=False,
                error=str(exc),
            )
        return EscalationRoute(
            channel=str(result.get("channel", "mock_webhook")),
            severity=str(result.get("severity", "info")),
            notify=[str(x) for x in (result.get("notify") or ["ops"])],
            policy=str(result.get("policy", "unknown")),
            ready=True,
        )

    def ready(self) -> bool:
        bin_ok = bool(shutil.which(self._opa) or Path(self._opa).is_file())
        return self._policy_dir.is_dir() and bin_ok

    @property
    def mode(self) -> str:
        return "eval"

    @property
    def policy_dir(self) -> str:
        return str(self._policy_dir)


def resolve_policy_dir(explicit: Path | None = None) -> Path:
    if explicit is not None:
        return explicit
    env = os.getenv("PRISM_OPA_POLICY_DIR", "").strip()
    if env:
        return Path(env)
    return _DEFAULT_POLICY_DIR


def build_policy_engine(
    *,
    opa_url: str | None = None,
    policy_dir: Path | None = None,
    opa_bin: str | None = None,
) -> PolicyEngine:
    """Prefer HTTP (Compose), else local ``opa eval``, else unavailable."""
    url = (opa_url if opa_url is not None else os.getenv("PRISM_OPA_URL", "")).strip()
    pdir = resolve_policy_dir(policy_dir)
    if url:
        return HttpPolicyEngine(url, pdir)

    bin_path = opa_bin or os.getenv("PRISM_OPA_BIN", "").strip() or shutil.which("opa")
    if bin_path and pdir.is_dir():
        return EvalPolicyEngine(bin_path, pdir)

    log.warning("No PRISM_OPA_URL and no local opa binary/policy dir — trip decisions fail open")
    return UnavailablePolicyEngine()
