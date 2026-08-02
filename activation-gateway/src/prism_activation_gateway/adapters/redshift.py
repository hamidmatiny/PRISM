"""Redshift adapter — zero-ETL / auto-copy preferred, COPY Parquet fallback."""

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


class RedshiftAdapter:
    warehouse_id = WarehouseId.REDSHIFT.value
    display_name = "Amazon Redshift Serverless"
    preferred_strategy = "zero_etl"
    storage_mode = StorageMode.MATERIALIZED_COPY.value

    def __init__(self, endpoint: str, *, client: httpx.Client | None = None) -> None:
        self.endpoint = endpoint.rstrip("/")
        self._client = client or httpx.Client(timeout=30.0)

    def health(self) -> dict[str, Any]:
        response = self._client.get(f"{self.endpoint}/health")
        response.raise_for_status()
        return response.json()

    def activate(self, request: ActivateRequest) -> ActivateResponse:
        strategy = request.strategy
        if strategy == ActivationStrategy.ICEBERG_REST:
            raise ValueError("redshift adapter does not support iceberg_rest")

        # Prefer zero-ETL; fall back to COPY when forced or when zero-ETL fails.
        attempted = (
            ["zero_etl", "copy"] if strategy == ActivationStrategy.AUTO else [strategy.value]
        )
        last_error: Exception | None = None
        payload: dict[str, Any] | None = None
        for strat in attempted:
            try:
                response = self._client.post(
                    f"{self.endpoint}/v1/activate",
                    json={
                        "table": request.gold_table,
                        "gold_uri": request.gold_uri,
                        "strategy": strat,
                    },
                )
                if response.status_code >= 400:
                    last_error = RuntimeError(response.json().get("detail", response.text))
                    continue
                payload = response.json()
                break
            except httpx.HTTPError as exc:
                last_error = exc
        if payload is None:
            raise RuntimeError(f"redshift activate failed: {last_error}")

        return ActivateResponse(
            activation_id=payload["activation_id"],
            gold_table=request.gold_table,
            warehouse=WarehouseId.REDSHIFT,
            strategy_used=payload["strategy_used"],
            storage_mode=StorageMode.MATERIALIZED_COPY,
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
            warehouse=WarehouseId.REDSHIFT,
            columns=list(payload["columns"]),
            rows=list(payload["rows"]),
            row_count=int(payload["row_count"]),
            storage_mode=StorageMode.MATERIALIZED_COPY,
            sql=payload.get("sql"),
        )


def _parse_ts(value: str) -> datetime:
    if value.endswith("Z"):
        value = value[:-1] + "+00:00"
    return datetime.fromisoformat(value)
