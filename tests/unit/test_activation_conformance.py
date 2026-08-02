"""
Warehouse adapter conformance suite.

Same discipline as Vulcan's serving/common conformance tests, applied to
warehouses: run the identical query against Redshift and Snowflake adapters
(local mocked endpoints) and assert equivalent results.

No invented throughput / cost numbers — structural equivalence only (ADR-001).
"""

from __future__ import annotations

import socket
import threading
from pathlib import Path
from typing import Any

import httpx
import pytest
import uvicorn
from fastapi.testclient import TestClient

from prism_activation_gateway.adapters.redshift import RedshiftAdapter
from prism_activation_gateway.adapters.snowflake import SnowflakeAdapter
from prism_activation_gateway.api import create_app
from prism_activation_gateway.config import GatewayConfig
from prism_activation_gateway.mocks.redshift_endpoint import create_redshift_mock_app
from prism_activation_gateway.mocks.snowflake_endpoint import create_snowflake_mock_app
from prism_activation_gateway.registry import RoutingRegistry

ROOT = Path(__file__).resolve().parents[2]
FIXTURE_GOLD = ROOT / "activation-gateway" / "fixtures" / "gold"
ASSET_URI = (FIXTURE_GOLD / "asset_daily_metrics").resolve().as_uri()

CONFORMANCE_SQL = """
SELECT asset_id, metric_date, ping_count, avg_speed_mph
FROM asset_daily_metrics
ORDER BY asset_id, metric_date
""".strip()


def _free_port() -> int:
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


def _wait_healthy(url: str) -> None:
    with httpx.Client() as client:
        for _ in range(80):
            try:
                if client.get(f"{url}/health", timeout=0.2).status_code == 200:
                    return
            except Exception:  # noqa: BLE001
                pass
        raise RuntimeError(f"mock not healthy: {url}")


@pytest.fixture()
def dual_gateway(tmp_path: Path):
    rs_port, sf_port = _free_port(), _free_port()
    rs_url, sf_url = f"http://127.0.0.1:{rs_port}", f"http://127.0.0.1:{sf_port}"
    rs_server = uvicorn.Server(
        uvicorn.Config(
            create_redshift_mock_app(), host="127.0.0.1", port=rs_port, log_level="warning"
        )
    )
    sf_server = uvicorn.Server(
        uvicorn.Config(
            create_snowflake_mock_app(), host="127.0.0.1", port=sf_port, log_level="warning"
        )
    )
    threading.Thread(target=rs_server.run, daemon=True).start()
    threading.Thread(target=sf_server.run, daemon=True).start()
    _wait_healthy(rs_url)
    _wait_healthy(sf_url)

    cfg = GatewayConfig(
        mode="mock",
        gold_root=FIXTURE_GOLD,
        fixture_gold_root=FIXTURE_GOLD,
        redshift_endpoint=rs_url,
        snowflake_endpoint=sf_url,
        start_embedded_mocks=False,
        routing_state_path=tmp_path / "routing.json",
    )
    app = create_app(
        cfg,
        redshift=RedshiftAdapter(rs_url),
        snowflake=SnowflakeAdapter(sf_url),
        registry=RoutingRegistry(cfg.routing_state_path),
    )
    client = TestClient(app)
    yield client
    rs_server.should_exit = True
    sf_server.should_exit = True


def _canonicalize(result: dict[str, Any]) -> tuple[tuple[str, ...], tuple[tuple[Any, ...], ...]]:
    columns = tuple(result["columns"])
    rows = tuple(tuple(_norm(v) for v in row) for row in result["rows"])
    return columns, rows


def _norm(value: Any) -> Any:
    if value is None:
        return None
    if isinstance(value, float):
        return round(value, 6)
    text = str(value)
    # Normalize date / timestamp string forms across adapters.
    if "T" in text:
        return text.replace("T", " ").rstrip("Z")
    return text


def test_conformance_identical_query_equivalent_results(dual_gateway: TestClient) -> None:
    """Activate the same gold table into both warehouses; assert query parity."""
    client = dual_gateway
    for warehouse in ("redshift", "snowflake"):
        response = client.post(
            "/v1/activate",
            json={
                "gold_table": "asset_daily_metrics",
                "warehouse": warehouse,
                "gold_uri": ASSET_URI,
                "strategy": "auto",
                "set_primary": warehouse == "redshift",
            },
        )
        assert response.status_code == 200, response.text
        assert response.json()["row_count"] == 3

    rs = client.post(
        "/v1/query",
        json={
            "table": "asset_daily_metrics",
            "warehouse": "redshift",
            "sql": CONFORMANCE_SQL,
            "limit": 100,
        },
    )
    sf = client.post(
        "/v1/query",
        json={
            "table": "asset_daily_metrics",
            "warehouse": "snowflake",
            "sql": CONFORMANCE_SQL,
            "limit": 100,
        },
    )
    assert rs.status_code == 200, rs.text
    assert sf.status_code == 200, sf.text

    rs_body, sf_body = rs.json(), sf.json()
    assert rs_body["storage_mode"] == "materialized_copy"
    assert sf_body["storage_mode"] == "zero_copy"

    assert _canonicalize(rs_body) == _canonicalize(sf_body)
    assert rs_body["row_count"] == sf_body["row_count"] == 3


def test_conformance_storage_modes_differ_but_answers_match(dual_gateway: TestClient) -> None:
    """Prism property: different warehouse storage strategies, same logical answer."""
    client = dual_gateway
    for warehouse in ("redshift", "snowflake"):
        assert (
            client.post(
                "/v1/activate",
                json={
                    "gold_table": "asset_daily_metrics",
                    "warehouse": warehouse,
                    "gold_uri": ASSET_URI,
                },
            ).status_code
            == 200
        )

    sql = "SELECT COUNT(*) AS n FROM asset_daily_metrics"
    rs = client.post(
        "/v1/query",
        json={"table": "asset_daily_metrics", "warehouse": "redshift", "sql": sql},
    ).json()
    sf = client.post(
        "/v1/query",
        json={"table": "asset_daily_metrics", "warehouse": "snowflake", "sql": sql},
    ).json()
    assert rs["rows"] == sf["rows"]
    assert rs["rows"][0][0] == 3
    assert rs["storage_mode"] != sf["storage_mode"]
