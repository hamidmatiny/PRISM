"""Mock webhook receiver + inbox (ADR-001: no real Slack/PagerDuty).

incident-engine "delivers" alerts by calling its own mock receiver endpoint
over loopback HTTP -- a real network round-trip through FastAPI's routing,
just never leaving localhost -- and every delivery lands in a durable inbox
file you can inspect. This proves the alerting hook is real and wired
correctly without needing (or paying for) a real notification provider.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

import httpx

logger = logging.getLogger(__name__)


class WebhookSender:
    def __init__(self, inbox_path: Path, *, receiver_url: str | None = None) -> None:
        self.inbox_path = inbox_path
        self.inbox_path.parent.mkdir(parents=True, exist_ok=True)
        if not self.inbox_path.exists():
            self.inbox_path.write_text("", encoding="utf-8")
        self.receiver_url = receiver_url  # set after the app knows its own bind address

    def notify(self, payload: dict[str, Any]) -> None:
        if self.receiver_url:
            try:
                httpx.post(
                    f"{self.receiver_url}/v1/webhook-test/receive", json=payload, timeout=2.0
                )
                return
            except Exception as exc:  # noqa: BLE001 — never let alerting break the FSM
                logger.warning("mock webhook delivery failed, writing inbox directly: %s", exc)
        self.deliver(payload)

    def deliver(self, payload: dict[str, Any]) -> dict[str, Any]:
        with self.inbox_path.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(payload, sort_keys=True) + "\n")
        return payload

    def inbox(self, limit: int = 100) -> list[dict[str, Any]]:
        if not self.inbox_path.exists():
            return []
        lines = self.inbox_path.read_text(encoding="utf-8").splitlines()
        return [json.loads(line) for line in lines[-limit:]]
