# orchestration

Dagster asset-graph for PRISM (Phase 17 / [ADR-006](../docs/adr/006-dagster-orchestration.md)).

Wraps existing lakehouse medallion transforms, polls drift-monitor, and optionally
triggers a scenario-engine `drift_signature` reseed — **flag-gated**, never a
fake success when off ([ADR-005](../docs/adr/005-earned-evidence-policy.md)).

| | |
|---|---|
| **Port (host)** | **9112** (optional Compose profile `dagster`) |
| **Module** | `prism_orchestration.definitions` |
| **CLI** | `python -m prism_orchestration` |

## Assets

| Asset | What it does |
|-------|----------------|
| `lakehouse_medallion` | Calls `prism_lakehouse.transforms.run_medallion` |
| `drift_status_snapshot` | `GET {drift-monitor}/v1/status` |
| `scenario_drift_reseed` | If `PRISM_DAGSTER_DRIFT_RESEED=1` **and** snapshot shows drift → `POST /v1/reset` with `drift_signature` weights + pull N events; otherwise honest `skipped` |

## Env

| Var | Default | Role |
|-----|---------|------|
| `PRISM_ORCH_BRONZE_ROOT` | `lakehouse/fixtures/bronze` | Medallion input |
| `PRISM_ORCH_WAREHOUSE_ROOT` | `.data/lakehouse-from-orchestration` | Medallion output |
| `PRISM_DRIFT_MONITOR_URL` | `http://127.0.0.1:9109` | Drift poll |
| `PRISM_SCENARIO_URL` | `http://127.0.0.1:9107` | Reseed target |
| `PRISM_DAGSTER_DRIFT_RESEED` | off | Must be `1`/`true` to attempt reseed |

## Test it yourself

```bash
pip install -e lakehouse -e "orchestration[web]"
# Flag off — reseed must report skipped/flag_off:
PRISM_DAGSTER_DRIFT_RESEED=0 python -m prism_orchestration --select scenario_drift_reseed

# Full graph (Spark needs Java 17; otherwise lakehouse asset skips honestly):
python -m prism_orchestration

# Optional UI:
docker compose --profile dagster up -d --build orchestration
open http://127.0.0.1:9112
```
