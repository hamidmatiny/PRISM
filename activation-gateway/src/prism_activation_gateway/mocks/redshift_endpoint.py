"""
Mock Redshift Serverless endpoint.

Simulates zero-ETL / auto-copy and COPY-from-Parquet into a materialized DuckDB
store. This is an HTTP stand-in for CI/local — never a real Redshift workgroup
(ADR-001).
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
    strategy: str = "auto"  # auto | zero_etl | copy


class QueryBody(BaseModel):
    table: str
    sql: str | None = None
    limit: int = Field(default=100, ge=1, le=1000)


class RedshiftMockState:
    def __init__(self) -> None:
        # In-memory DuckDB = "Redshift" materialization target.
        self.con = duckdb.connect(database=":memory:")
        self.tables: dict[str, dict[str, Any]] = {}

    def activate(self, body: ActivateBody) -> dict[str, Any]:
        path = assert_gold_readable(body.gold_uri)
        strategy = body.strategy
        if strategy == "auto":
            strategy = "zero_etl"
        if strategy not in {"zero_etl", "copy"}:
            raise HTTPException(
                status_code=400,
                detail=f"redshift mock does not support strategy={strategy!r}",
            )

        # Materialize: COPY parquet into a physical table (simulates zero-ETL sink
        # or explicit COPY). Storage is duplicated inside this mock warehouse.
        self.con.execute(f'DROP TABLE IF EXISTS "{body.table}"')
        self.con.execute(
            f"""
            CREATE TABLE "{body.table}" AS
            SELECT * FROM read_parquet(?)
            """,
            [str(path / "**/*.parquet")],
        )
        row_count = int(self.con.execute(f'SELECT COUNT(*) FROM "{body.table}"').fetchone()[0])
        meta = {
            "table": body.table,
            "gold_uri": body.gold_uri,
            "strategy_used": strategy,
            "storage_mode": "materialized_copy",
            "row_count": row_count,
            "activation_id": f"act_{uuid4().hex[:12]}",
            "activated_at": datetime.now(tz=UTC).isoformat().replace("+00:00", "Z"),
            "status": "active",
        }
        self.tables[body.table] = meta
        return meta

    def query(self, body: QueryBody) -> dict[str, Any]:
        if body.table not in self.tables:
            raise HTTPException(status_code=404, detail=f"table not activated: {body.table}")
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
        meta = self.tables[body.table]
        return {
            "table": body.table,
            "warehouse": "redshift",
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


def create_redshift_mock_app(state: RedshiftMockState | None = None) -> FastAPI:
    store = state or RedshiftMockState()
    app = FastAPI(title="PRISM Mock Redshift", version="0.1.0")
    app.state.store = store

    @app.get("/health")
    def health() -> dict[str, Any]:
        return {
            "status": "ok",
            "warehouse": "redshift",
            "tables": sorted(store.tables),
        }

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
