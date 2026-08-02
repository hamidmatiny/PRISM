"""Activation gateway unit tests — contract shape + adapter wiring (structural)."""

from __future__ import annotations

from pathlib import Path

import httpx
import pytest
import uvicorn
from fastapi.testclient import TestClient

from prism_activation_contract import ActivateRequest, WarehouseId, openapi_path
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


@pytest.fixture()
def mock_endpoints(tmp_path: Path):
    import socket
    import threading

    def _free_port() -> int:
        with socket.socket() as s:
            s.bind(("127.0.0.1", 0))
            return int(s.getsockname()[1])

    rs_app = create_redshift_mock_app()
    sf_app = create_snowflake_mock_app()
    rs_port = _free_port()
    sf_port = _free_port()
    rs_server = uvicorn.Server(
        uvicorn.Config(rs_app, host="127.0.0.1", port=rs_port, log_level="warning")
    )
    sf_server = uvicorn.Server(
        uvicorn.Config(sf_app, host="127.0.0.1", port=sf_port, log_level="warning")
    )
    threads = [
        threading.Thread(target=rs_server.run, daemon=True),
        threading.Thread(target=sf_server.run, daemon=True),
    ]
    for t in threads:
        t.start()

    rs_url = f"http://127.0.0.1:{rs_port}"
    sf_url = f"http://127.0.0.1:{sf_port}"
    with httpx.Client() as client:
        for url in (rs_url, sf_url):
            for _ in range(80):
                try:
                    if client.get(f"{url}/health", timeout=0.2).status_code == 200:
                        break
                except Exception:  # noqa: BLE001
                    pass
            else:
                raise RuntimeError(f"mock failed to start: {url}")

    cfg = GatewayConfig(
        port=9103,
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
    yield {
        "client": TestClient(app),
        "rs_url": rs_url,
        "sf_url": sf_url,
        "config": cfg,
    }
    rs_server.should_exit = True
    sf_server.should_exit = True


def test_openapi_contract_file_exists() -> None:
    path = openapi_path()
    text = path.read_text(encoding="utf-8")
    assert "POST" in text or "post:" in text
    assert "/v1/activate" in text
    assert "/v1/query" in text
    assert "redshift" in text and "snowflake" in text


def test_health_and_warehouses(mock_endpoints) -> None:
    client: TestClient = mock_endpoints["client"]
    health = client.get("/health")
    assert health.status_code == 200
    body = health.json()
    assert body["service"] == "activation-gateway"
    assert body["warehouses"]["redshift"] == "ok"
    assert body["warehouses"]["snowflake"] == "ok"

    warehouses = client.get("/v1/warehouses").json()["warehouses"]
    ids = {w["id"] for w in warehouses}
    assert ids == {"redshift", "snowflake"}
    modes = {w["id"]: w["storage_mode"] for w in warehouses}
    assert modes["redshift"] == "materialized_copy"
    assert modes["snowflake"] == "zero_copy"


def test_activate_redshift_and_snowflake(mock_endpoints) -> None:
    client: TestClient = mock_endpoints["client"]
    rs = client.post(
        "/v1/activate",
        json={
            "gold_table": "asset_daily_metrics",
            "warehouse": "redshift",
            "gold_uri": ASSET_URI,
            "strategy": "auto",
            "set_primary": True,
        },
    )
    assert rs.status_code == 200, rs.text
    rs_body = rs.json()
    assert rs_body["storage_mode"] == "materialized_copy"
    assert rs_body["strategy_used"] in {"zero_etl", "copy"}
    assert rs_body["row_count"] == 3

    sf = client.post(
        "/v1/activate",
        json={
            "gold_table": "asset_daily_metrics",
            "warehouse": "snowflake",
            "gold_uri": ASSET_URI,
            "strategy": "iceberg_rest",
            "set_primary": False,
        },
    )
    assert sf.status_code == 200, sf.text
    sf_body = sf.json()
    assert sf_body["storage_mode"] == "zero_copy"
    assert sf_body["strategy_used"] == "iceberg_rest"
    assert sf_body["row_count"] == 3

    routing = client.get("/v1/routing/asset_daily_metrics")
    assert routing.status_code == 200
    assert routing.json()["primary_warehouse"] == "redshift"
    assert len(routing.json()["warehouses"]) == 2


def test_query_auto_routes_to_primary(mock_endpoints) -> None:
    client: TestClient = mock_endpoints["client"]
    client.post(
        "/v1/activate",
        json={
            "gold_table": "asset_daily_metrics",
            "warehouse": "redshift",
            "gold_uri": ASSET_URI,
            "set_primary": True,
        },
    )
    client.post(
        "/v1/activate",
        json={
            "gold_table": "asset_daily_metrics",
            "warehouse": "snowflake",
            "gold_uri": ASSET_URI,
            "set_primary": False,
        },
    )
    result = client.post(
        "/v1/query",
        json={
            "table": "asset_daily_metrics",
            "warehouse": "auto",
            "sql": "SELECT asset_id FROM asset_daily_metrics ORDER BY asset_id",
            "limit": 10,
        },
    )
    assert result.status_code == 200, result.text
    body = result.json()
    assert body["warehouse"] == "redshift"
    assert body["row_count"] == 3
    assert body["columns"] == ["asset_id"]


def test_snowflake_rejects_copy_strategy() -> None:
    from prism_activation_contract import ActivationStrategy

    req = ActivateRequest(
        gold_table="asset_daily_metrics",
        warehouse=WarehouseId.SNOWFLAKE,
        gold_uri=ASSET_URI,
        strategy=ActivationStrategy.COPY,
    )
    adapter = SnowflakeAdapter("http://127.0.0.1:9")
    with pytest.raises(ValueError, match="zero-copy"):
        adapter.activate(req)
