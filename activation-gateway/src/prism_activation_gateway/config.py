"""Environment configuration for the activation gateway."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


def _default_gold_root() -> Path:
    data = Path(os.environ.get("PRISM_DATA_ROOT", ".data"))
    lake = Path(os.environ.get("PRISM_LAKEHOUSE_ROOT", data / "lakehouse"))
    return lake / "gold"


@dataclass(frozen=True)
class GatewayConfig:
    port: int = 9103
    mode: str = "mock"  # mock | live
    gold_root: Path = Path(".data/lakehouse/gold")
    fixture_gold_root: Path | None = None
    redshift_endpoint: str = "http://127.0.0.1:9110"
    snowflake_endpoint: str = "http://127.0.0.1:9111"
    start_embedded_mocks: bool = True
    routing_state_path: Path = Path(".data/activation/routing.json")

    @classmethod
    def from_env(cls) -> GatewayConfig:
        data_root = Path(os.environ.get("PRISM_DATA_ROOT", ".data"))
        gold = Path(os.environ.get("PRISM_ACTIVATION_GOLD_ROOT", str(_default_gold_root())))
        fixture = os.environ.get("PRISM_ACTIVATION_FIXTURE_GOLD")
        mode = os.environ.get("PRISM_ACTIVATION_MODE", "mock").lower()
        return cls(
            port=int(os.environ.get("PRISM_ACTIVATION_GATEWAY_PORT", "9103")),
            mode=mode,
            gold_root=gold,
            fixture_gold_root=Path(fixture) if fixture else None,
            redshift_endpoint=os.environ.get("PRISM_MOCK_REDSHIFT_URL", "http://127.0.0.1:9110"),
            snowflake_endpoint=os.environ.get("PRISM_MOCK_SNOWFLAKE_URL", "http://127.0.0.1:9111"),
            start_embedded_mocks=os.environ.get("PRISM_ACTIVATION_EMBEDDED_MOCKS", "1")
            not in {"0", "false", "False"},
            routing_state_path=Path(
                os.environ.get(
                    "PRISM_ACTIVATION_ROUTING_PATH",
                    str(data_root / "activation" / "routing.json"),
                )
            ),
        )

    def resolve_gold_uri(self, gold_table: str, gold_uri: str | None = None) -> str:
        if gold_uri:
            return gold_uri
        # Prefer lakehouse gold, fall back to packaged fixtures.
        candidates = [
            self.gold_root / gold_table,
        ]
        if self.fixture_gold_root is not None:
            candidates.append(self.fixture_gold_root / gold_table)
        for path in candidates:
            if path.exists():
                return path.resolve().as_uri()
        raise FileNotFoundError(f"gold table {gold_table!r} not found under {self.gold_root}")
