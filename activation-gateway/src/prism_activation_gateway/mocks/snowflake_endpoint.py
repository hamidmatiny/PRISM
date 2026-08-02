"""
Mock Snowflake Horizon Catalog / Iceberg REST endpoint.

Registers gold parquet paths as zero-copy external relations (DuckDB views over
the same files). Does **not** duplicate storage — the mock keeps only a catalog
pointer to the gold URI (ADR-style zero-copy).
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

import duckdb
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

from prism_activation_gateway.gold import assert_gold_readable
from prism_activation_gateway.mocks.sql_guard import normalize_select


class ActivateBody(BaseModel):
    table: str
    gold_uri: str
    strategy: str = "iceberg_rest"  # iceberg_rest only for snowflake


class QueryBody(BaseModel):
    table: str
    sql: str | None = None
    limit: int = Field(default=100, ge=1, le=1000)


class SnowflakeMockState:
    def __init__(self) -> None:
        self.con = duckdb.connect(database=":memory:")
        # Catalog only — values are gold path pointers, not copied row stores.
        self.catalog: dict[str, dict[str, Any]] = {}

    def activate(self, body: ActivateBody) -> dict[str, Any]:
        path = assert_gold_readable(body.gold_uri)
        strategy = body.strategy
        if strategy in {"auto", "iceberg_rest"}:
            strategy = "iceberg_rest"
        else:
            raise HTTPException(
                status_code=400,
                detail=(
                    "snowflake mock supports iceberg_rest / Horizon Catalog "
                    f"zero-copy only (got {strategy!r})"
                ),
            )

        # Zero-copy: VIEW over parquet files — no CREATE TABLE AS SELECT materialization.
        self.con.execute(f'DROP VIEW IF EXISTS "{body.table}"')
        # DuckDB view binding; path stays the source of truth.
        parquet_glob = str(path / "**/*.parquet").replace("'", "''")
        self.con.execute(
            f"""
            CREATE VIEW "{body.table}" AS
            SELECT * FROM read_parquet('{parquet_glob}')
            """
        )
        row_count = int(self.con.execute(f'SELECT COUNT(*) FROM "{body.table}"').fetchone()[0])
        meta = {
            "table": body.table,
            "gold_uri": body.gold_uri,
            "strategy_used": strategy,
            "storage_mode": "zero_copy",
            "row_count": row_count,
            "activation_id": f"act_{uuid4().hex[:12]}",
            "activated_at": datetime.now(tz=UTC).isoformat().replace("+00:00", "Z"),
            "status": "active",
            "catalog": "horizon",
            "iceberg_rest": True,
            "source_path": str(path),
        }
        self.catalog[body.table] = meta
        return meta

    def query(self, body: QueryBody) -> dict[str, Any]:
        if body.table not in self.catalog:
            raise HTTPException(status_code=404, detail=f"table not registered: {body.table}")
        try:
            sql = normalize_select(body.sql or "", default_table=body.table, limit=body.limit)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        try:
            relation = self.con.execute(sql)
        except duckdb.Error as exc:
            raise HTTPException(status_code=400, detail=f"sql error: {exc}") from exc
        columns = [d[0] for d in relation.description]
        rows = [list(_jsonable(v) for v in row) for row in relation.fetchall()]
        meta = self.catalog[body.table]
        return {
            "table": body.table,
            "warehouse": "snowflake",
            "columns": columns,
            "rows": rows,
            "row_count": len(rows),
            "storage_mode": meta["storage_mode"],
            "sql": sql,
        }


def _jsonable(value: Any) -> Any:
    if hasattr(value, "isoformat"):
        return value.isoformat()
    return value


def create_snowflake_mock_app(state: SnowflakeMockState | None = None) -> FastAPI:
    store = state or SnowflakeMockState()
    app = FastAPI(title="PRISM Mock Snowflake", version="0.1.0")
    app.state.store = store

    @app.get("/health")
    def health() -> dict[str, Any]:
        return {
            "status": "ok",
            "warehouse": "snowflake",
            "catalog": "horizon",
            "tables": sorted(store.catalog),
        }

    @app.get("/iceberg/v1/config")
    def iceberg_config() -> dict[str, Any]:
        """Minimal Iceberg REST catalog discovery stub."""
        return {"defaults": {}, "overrides": {}, "endpoints": ["POST /v1/activate"]}

    @app.post("/v1/activate")
    def activate(body: ActivateBody) -> dict[str, Any]:
        try:
            return store.activate(body)
        except FileNotFoundError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc

    @app.post("/v1/query")
    def query(body: QueryBody) -> dict[str, Any]:
        return store.query(body)

    return app
