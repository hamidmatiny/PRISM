"""Snowflake adapter — Iceberg REST / Horizon Catalog zero-copy (no storage dup)."""

from __future__ import annotations

from datetime import datetime
from typing import Any

import httpx

from prism_activation_contract import (
    ActivateRequest,
    ActivateResponse,
    ActivationStrategy,
    QueryRequest,
    QueryResponse,
    StorageMode,
    WarehouseId,
)


class SnowflakeAdapter:
    warehouse_id = WarehouseId.SNOWFLAKE.value
    display_name = "Snowflake (Horizon Catalog / Iceberg REST)"
    preferred_strategy = "iceberg_rest"
    storage_mode = StorageMode.ZERO_COPY.value

    def __init__(self, endpoint: str, *, client: httpx.Client | None = None) -> None:
        self.endpoint = endpoint.rstrip("/")
        self._client = client or httpx.Client(timeout=30.0)

    def health(self) -> dict[str, Any]:
        response = self._client.get(f"{self.endpoint}/health")
        response.raise_for_status()
        return response.json()

    def activate(self, request: ActivateRequest) -> ActivateResponse:
        if request.strategy in {ActivationStrategy.ZERO_ETL, ActivationStrategy.COPY}:
            raise ValueError(
                "snowflake adapter is zero-copy only (iceberg_rest / Horizon Catalog); "
                "do not duplicate gold storage"
            )
        strategy = (
            "iceberg_rest"
            if request.strategy in {ActivationStrategy.AUTO, ActivationStrategy.ICEBERG_REST}
            else request.strategy.value
        )
        response = self._client.post(
            f"{self.endpoint}/v1/activate",
            json={
                "table": request.gold_table,
                "gold_uri": request.gold_uri,
                "strategy": strategy,
            },
        )
        if response.status_code >= 400:
            raise RuntimeError(response.json().get("detail", response.text))
        payload = response.json()
        if payload.get("storage_mode") != "zero_copy":
            raise RuntimeError("snowflake activation must remain zero_copy")

        return ActivateResponse(
            activation_id=payload["activation_id"],
            gold_table=request.gold_table,
            warehouse=WarehouseId.SNOWFLAKE,
            strategy_used=payload["strategy_used"],
            storage_mode=StorageMode.ZERO_COPY,
            status="active",
            gold_uri=request.gold_uri,
            row_count=int(payload["row_count"]),
            activated_at=_parse_ts(payload["activated_at"]),
            primary=request.set_primary,
        )

    def query(self, request: QueryRequest) -> QueryResponse:
        response = self._client.post(
            f"{self.endpoint}/v1/query",
            json={
                "table": request.table,
                "sql": request.sql,
                "limit": request.limit,
            },
        )
        if response.status_code == 404:
            raise LookupError(response.json().get("detail", "not found"))
        if response.status_code >= 400:
            raise ValueError(response.json().get("detail", response.text))
        payload = response.json()
        return QueryResponse(
            table=payload["table"],
            warehouse=WarehouseId.SNOWFLAKE,
            columns=list(payload["columns"]),
            rows=list(payload["rows"]),
            row_count=int(payload["row_count"]),
            storage_mode=StorageMode.ZERO_COPY,
            sql=payload.get("sql"),
        )


def _parse_ts(value: str) -> datetime:
    if value.endswith("Z"):
        value = value[:-1] + "+00:00"
    return datetime.fromisoformat(value)
