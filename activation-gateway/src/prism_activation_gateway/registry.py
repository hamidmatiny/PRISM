"""Persistent routing registry: which warehouse currently serves table X."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from prism_activation_contract import (
    ActivateResponse,
    RoutingEntry,
    RoutingResponse,
    StorageMode,
    WarehouseId,
)


class RoutingRegistry:
    def __init__(self, path: Path) -> None:
        self.path = path
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._data: dict[str, Any] = {"tables": {}}
        self._load()

    def _load(self) -> None:
        if self.path.is_file():
            self._data = json.loads(self.path.read_text(encoding="utf-8"))

    def _save(self) -> None:
        self.path.write_text(
            json.dumps(self._data, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )

    def record(self, activation: ActivateResponse, *, set_primary: bool) -> None:
        tables: dict[str, Any] = self._data.setdefault("tables", {})
        entry = tables.setdefault(activation.gold_table, {"warehouses": {}, "primary": None})
        entry["warehouses"][activation.warehouse.value] = {
            "warehouse": activation.warehouse.value,
            "status": activation.status,
            "storage_mode": activation.storage_mode.value,
            "gold_uri": activation.gold_uri,
            "strategy_used": activation.strategy_used,
            "row_count": activation.row_count,
            "activation_id": activation.activation_id,
            "activated_at": activation.activated_at.isoformat(),
        }
        if set_primary or entry.get("primary") is None:
            entry["primary"] = activation.warehouse.value
        self._save()

    def primary_for(self, table: str) -> WarehouseId | None:
        entry = self._data.get("tables", {}).get(table)
        if not entry or not entry.get("primary"):
            return None
        return WarehouseId(entry["primary"])

    def routing_for(self, table: str) -> RoutingResponse:
        entry = self._data.get("tables", {}).get(table)
        if not entry:
            raise LookupError(f"no activations for table {table!r}")
        warehouses: list[RoutingEntry] = []
        primary = entry.get("primary")
        for wid, meta in entry.get("warehouses", {}).items():
            warehouses.append(
                RoutingEntry(
                    warehouse=WarehouseId(wid),
                    status=meta.get("status", "active"),
                    storage_mode=StorageMode(meta["storage_mode"]),
                    primary=(wid == primary),
                    gold_uri=meta["gold_uri"],
                    strategy_used=meta.get("strategy_used"),
                    row_count=meta.get("row_count"),
                    activation_id=meta.get("activation_id"),
                )
            )
        warehouses.sort(key=lambda w: w.warehouse.value)
        return RoutingResponse(
            table=table,
            primary_warehouse=WarehouseId(primary) if primary else None,
            warehouses=warehouses,
        )
