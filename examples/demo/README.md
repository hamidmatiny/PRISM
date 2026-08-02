# PRISM demo seed

Realistic local dataset for `make demo` and the Phase 11 golden-path e2e.

| Artifact | Purpose |
|----------|---------|
| `seed.py` | Materialize `.data/` gold + bootstrap control-plane assets/WOs |
| `run_demo.sh` | Bring the stack up with `docker-compose.demo.yml` in **&lt; 5 minutes** |
| `assets.json` | Fleet assets shown in the cockpit |
| `work_orders.json` | Open work orders driving twin health |

Gold metrics start from `activation-gateway/fixtures/gold/asset_daily_metrics`
and land at `.data/lakehouse/gold/asset_daily_metrics/` so activation-gateway
serves the **same** table to Redshift and Snowflake mocks.
