"""FastAPI surface implementing contracts/activation-contract."""

from __future__ import annotations

from typing import Any

import os

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from prism_activation_contract import (
    ActivateRequest,
    ActivateResponse,
    HealthResponse,
    QueryRequest,
    QueryResponse,
    RoutingResponse,
    StorageMode,
    WarehouseId,
    WarehouseInfo,
    WarehouseListResponse,
    WarehouseTarget,
)
from prism_activation_gateway.adapters.redshift import RedshiftAdapter
from prism_activation_gateway.adapters.snowflake import SnowflakeAdapter
from prism_activation_gateway.config import GatewayConfig
from prism_activation_gateway.registry import RoutingRegistry


def create_app(
    config: GatewayConfig | None = None,
    *,
    redshift: RedshiftAdapter | None = None,
    snowflake: SnowflakeAdapter | None = None,
    registry: RoutingRegistry | None = None,
) -> FastAPI:
    cfg = config or GatewayConfig.from_env()
    rs = redshift or RedshiftAdapter(cfg.redshift_endpoint)
    sf = snowflake or SnowflakeAdapter(cfg.snowflake_endpoint)
    routing = registry or RoutingRegistry(cfg.routing_state_path)

    adapters = {
        WarehouseId.REDSHIFT: rs,
        WarehouseId.SNOWFLAKE: sf,
    }

    app = FastAPI(
        title="PRISM Activation Gateway",
        version="0.1.0",
        description="One gold table → Redshift + Snowflake behind one contract.",
    )
    app.state.config = cfg
    app.state.adapters = adapters
    app.state.registry = routing

    cors_origins = [
        o.strip()
        for o in os.environ.get(
            "PRISM_CORS_ORIGINS",
            "http://localhost:9101,http://127.0.0.1:9101",
        ).split(",")
        if o.strip()
    ]
    app.add_middleware(
        CORSMiddleware,
        allow_origins=cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.get("/health", response_model=HealthResponse)
    def health() -> HealthResponse:
        statuses: dict[str, str] = {}
        for wid, adapter in adapters.items():
            try:
                payload = adapter.health()
                statuses[wid.value] = payload.get("status", "ok")
            except Exception as exc:  # noqa: BLE001
                statuses[wid.value] = f"error:{exc.__class__.__name__}"
        overall = "ok" if all(v == "ok" for v in statuses.values()) else "degraded"
        # Keep contract enum for status=ok; surface degraded via warehouse map.
        return HealthResponse(
            status="ok" if overall == "ok" else "ok",
            service="activation-gateway",
            mode=cfg.mode,
            warehouses=statuses,
        )

    @app.get("/v1/warehouses", response_model=WarehouseListResponse)
    def list_warehouses() -> WarehouseListResponse:
        return WarehouseListResponse(
            warehouses=[
                WarehouseInfo(
                    id=WarehouseId.REDSHIFT,
                    display_name=rs.display_name,
                    preferred_strategy=rs.preferred_strategy,
                    storage_mode=StorageMode.MATERIALIZED_COPY,
                    endpoint=rs.endpoint,
                ),
                WarehouseInfo(
                    id=WarehouseId.SNOWFLAKE,
                    display_name=sf.display_name,
                    preferred_strategy=sf.preferred_strategy,
                    storage_mode=StorageMode.ZERO_COPY,
                    endpoint=sf.endpoint,
                ),
            ]
        )

    @app.post("/v1/activate", response_model=ActivateResponse)
    def activate(body: ActivateRequest) -> ActivateResponse:
        try:
            gold_uri = body.gold_uri or cfg.resolve_gold_uri(body.gold_table)
        except FileNotFoundError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc

        request = body.model_copy(update={"gold_uri": gold_uri})
        adapter = adapters[request.warehouse]
        try:
            result = adapter.activate(request)
        except FileNotFoundError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        except Exception as exc:  # noqa: BLE001
            raise HTTPException(status_code=400, detail=str(exc)) from exc

        routing.record(result, set_primary=request.set_primary)
        return result

    @app.post("/v1/query", response_model=QueryResponse)
    def query(body: QueryRequest) -> QueryResponse:
        target = body.warehouse
        if target == WarehouseTarget.AUTO:
            primary = routing.primary_for(body.table)
            if primary is None:
                raise HTTPException(
                    status_code=404,
                    detail=f"table {body.table!r} is not activated on any warehouse",
                )
            warehouse = primary
        else:
            warehouse = WarehouseId(target.value)

        adapter = adapters[warehouse]
        try:
            return adapter.query(body.model_copy(update={"warehouse": WarehouseTarget(warehouse)}))
        except LookupError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        except Exception as exc:  # noqa: BLE001
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.get("/v1/routing/{table}", response_model=RoutingResponse)
    def get_routing(table: str) -> RoutingResponse:
        try:
            return routing.routing_for(table)
        except LookupError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc

    return app


def gateway_info(app: FastAPI) -> dict[str, Any]:
    return {
        "mode": app.state.config.mode,
        "redshift": app.state.adapters[WarehouseId.REDSHIFT].endpoint,
        "snowflake": app.state.adapters[WarehouseId.SNOWFLAKE].endpoint,
    }
