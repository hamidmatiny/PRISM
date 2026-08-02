"""PRISM activation contract — warehouse-agnostic activate/query models."""

from __future__ import annotations

from importlib.resources import files
from pathlib import Path

from prism_activation_contract.models import (
    ActivateRequest,
    ActivateResponse,
    ActivationStrategy,
    HealthResponse,
    QueryRequest,
    QueryResponse,
    RoutingEntry,
    RoutingResponse,
    StorageMode,
    WarehouseId,
    WarehouseInfo,
    WarehouseListResponse,
    WarehouseTarget,
)

__all__ = [
    "ActivateRequest",
    "ActivateResponse",
    "ActivationStrategy",
    "HealthResponse",
    "QueryRequest",
    "QueryResponse",
    "RoutingEntry",
    "RoutingResponse",
    "StorageMode",
    "WarehouseId",
    "WarehouseInfo",
    "WarehouseListResponse",
    "WarehouseTarget",
    "openapi_path",
]


def openapi_path() -> Path:
    """Return the packaged OpenAPI YAML path (canonical contract source)."""
    return Path(str(files("prism_activation_contract").joinpath("openapi.yaml")))
