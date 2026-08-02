# activation-contract

**Status:** stub (Phase 0) — OpenAPI contract lands in Phase 4.

Will define the warehouse-agnostic surface:

- Activate gold table X into warehouse Y
- Query table X regardless of which warehouse currently serves it

Adapters (Redshift Serverless, Snowflake Horizon Catalog) implement this contract behind `activation-gateway/`.

**Health / port:** N/A (contract package; gateway serves HTTP in Phase 4 on host `9103`).
