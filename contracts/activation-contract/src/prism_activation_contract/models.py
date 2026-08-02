"""Pydantic models for the activation OpenAPI contract (keep in sync with openapi.yaml)."""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class WarehouseId(StrEnum):
    REDSHIFT = "redshift"
    SNOWFLAKE = "snowflake"


class WarehouseTarget(StrEnum):
    REDSHIFT = "redshift"
    SNOWFLAKE = "snowflake"
    AUTO = "auto"


class ActivationStrategy(StrEnum):
    AUTO = "auto"
    ZERO_ETL = "zero_etl"
    COPY = "copy"
    ICEBERG_REST = "iceberg_rest"


class StorageMode(StrEnum):
    MATERIALIZED_COPY = "materialized_copy"
    ZERO_COPY = "zero_copy"


class ActivateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    gold_table: str = Field(..., pattern=r"^[a-z][a-z0-9_]{1,63}$")
    warehouse: WarehouseId
    gold_uri: str = Field(..., min_length=1)
    strategy: ActivationStrategy = ActivationStrategy.AUTO
    set_primary: bool = True


class ActivateResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    activation_id: str = Field(..., pattern=r"^act_[0-9a-f]{12}$")
    gold_table: str
    warehouse: WarehouseId
    strategy_used: str
    storage_mode: StorageMode
    status: str = "active"
    gold_uri: str
    row_count: int = Field(..., ge=0)
    activated_at: datetime
    primary: bool = True


class QueryRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    table: str = Field(..., pattern=r"^[a-z][a-z0-9_]{1,63}$")
    warehouse: WarehouseTarget = WarehouseTarget.AUTO
    sql: str | None = None
    limit: int = Field(default=100, ge=1, le=1000)


class QueryResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    table: str
    warehouse: WarehouseId
    columns: list[str]
    rows: list[list[Any]]
    row_count: int = Field(..., ge=0)
    storage_mode: StorageMode
    sql: str | None = None


class RoutingEntry(BaseModel):
    model_config = ConfigDict(extra="forbid")

    warehouse: WarehouseId
    status: str = "active"
    storage_mode: StorageMode
    primary: bool
    gold_uri: str
    strategy_used: str | None = None
    row_count: int | None = Field(default=None, ge=0)
    activation_id: str | None = None


class RoutingResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    table: str
    primary_warehouse: WarehouseId | None = None
    warehouses: list[RoutingEntry]


class WarehouseInfo(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: WarehouseId
    display_name: str
    preferred_strategy: str
    storage_mode: StorageMode
    endpoint: str | None = None


class WarehouseListResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    warehouses: list[WarehouseInfo]


class HealthResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: str = "ok"
    service: str = "activation-gateway"
    mode: str | None = None
    warehouses: dict[str, str] | None = None
