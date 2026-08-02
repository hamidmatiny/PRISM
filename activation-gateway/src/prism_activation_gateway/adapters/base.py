"""Adapter protocol shared by Redshift and Snowflake implementations."""

from __future__ import annotations

from typing import Any, Protocol

from prism_activation_contract import ActivateRequest, ActivateResponse, QueryRequest, QueryResponse


class WarehouseAdapter(Protocol):
    warehouse_id: str
    display_name: str
    preferred_strategy: str
    storage_mode: str
    endpoint: str

    def health(self) -> dict[str, Any]: ...

    def activate(self, request: ActivateRequest) -> ActivateResponse: ...

    def query(self, request: QueryRequest) -> QueryResponse: ...
