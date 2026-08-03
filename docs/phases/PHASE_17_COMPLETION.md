# Phase 17 completion — Dagster orchestration

**Date:** 2026-08-03
**Status:** Complete
**Track:** v1.2.0 (Phases 16–19)

## What shipped

- **`orchestration/`** (new package, optional Compose profile `dagster`, host port **9112**) — Dagster asset graph for three real systems that previously had no shared dependency encoding:
  - `lakehouse_medallion` — calls existing `prism_lakehouse.transforms.run_medallion` (no fork of Spark transforms).
  - `drift_status_snapshot` — polls drift-monitor `GET /v1/status`; never invents `baseline_ready`.
  - `scenario_drift_reseed` — optional drift→scenario reseed edge, gated by `PRISM_DAGSTER_DRIFT_RESEED`.
- **[ADR-006](../adr/006-dagster-orchestration.md)** — honest justification: lakehouse work is asset-shaped, and lakehouse + drift-monitor + optional reseed need one graph instead of three ad-hoc scripts.
- **CLI:** `python -m prism_orchestration` materializes selected assets in-process and prints a JSON report of success + per-asset metadata (status / reason / counts). Used for local proof and CI-adjacent smoke without the web UI.
- **Flag-gated reseed (ADR-005):** when `PRISM_DAGSTER_DRIFT_RESEED` is off, `scenario_drift_reseed` returns `status=skipped`, `reason=flag_off`, `reseed_attempted=false` — a deliberate no-op that does not call drift-monitor or scenario-engine. When the flag is on but no drifted features are present, it returns `reason=no_drift_detected` and still does not reseed. Only flag-on **and** `drifted_feature_count >= 1` triggers `POST /v1/reset` with `drift_signature: 1.0` weights and a small pull of synthetic events (still `synthetic_scenario=true`).
- **scenario-engine:** `POST /v1/reset` accepts optional per-run `weights` (normalized via `normalize_weights`) so the reseed edge can request a focused `drift_signature` replay without restarting the container.
- **ADR-005 honesty on lakehouse / drift poll:** missing Java / JVM → lakehouse reports `skipped` (not `ok`); unreachable drift-monitor → snapshot reports `skipped` with the error string, never a fabricated baseline.
- **Wiring:** Compose profile `dagster`, CI `pip install -e orchestration` + `dagster>=1.8`, Makefile `phase17-check` + `setup` editable install, GHCR matrix includes `orchestration`, foundation tests require ADR-006 + `PHASE_17_COMPLETION.md` + `orchestration/` tree, ports documented in README / ARCHITECTURE / monorepo rule.

## Live proof — real commands, pasted output

**1. Flag off — reseed is a deliberate no-op (does not call scenario-engine):**

```bash
PRISM_DAGSTER_DRIFT_RESEED=0 python -m prism_orchestration --select scenario_drift_reseed
```

```json
{
  "success": true,
  "config": {
    "drift_reseed_enabled": false,
    "bronze_root": "lakehouse/fixtures/bronze",
    "warehouse_root": ".data/lakehouse-from-orchestration",
    "drift_monitor_url": "http://127.0.0.1:9109",
    "scenario_url": "http://127.0.0.1:9107"
  },
  "materializations": [
    {
      "asset": "scenario_drift_reseed",
      "metadata": {
        "status": "skipped",
        "reason": "flag_off",
        "flag": "PRISM_DAGSTER_DRIFT_RESEED",
        "reseed_attempted": false
      }
    }
  ]
}
```

**2. Lakehouse medallion actually materialized via Dagster (fixture bronze → warehouse counts):**

```bash
PRISM_ORCH_BRONZE_ROOT=lakehouse/fixtures/bronze \
PRISM_ORCH_WAREHOUSE_ROOT=.data/lakehouse-from-orchestration-proof \
python -m prism_orchestration --select lakehouse_medallion
```

```json
{
  "success": true,
  "materializations": [
    {
      "asset": "lakehouse_medallion",
      "metadata": {
        "status": "ok",
        "bronze_root": "lakehouse/fixtures/bronze",
        "warehouse_root": ".data/lakehouse-from-orchestration-proof",
        "counts": {
          "silver.sensor_pings": 3,
          "silver.camera_frames": 2,
          "gold.asset_daily_metrics": 2,
          "gold.fleet_frame_summary": 2
        }
      }
    }
  ]
}
```

**3. Live drift-monitor poll — honestly non-ready baseline (Compose `drift-monitor` up):**

```bash
curl -sS http://127.0.0.1:9109/health
python -m prism_orchestration --select drift_status_snapshot
```

```json
{"status":"ok","service":"drift-monitor","version":"0.16.0","baseline_ready":false,"assets":{}}
```

```json
{
  "success": true,
  "materializations": [
    {
      "asset": "drift_status_snapshot",
      "metadata": {
        "status": "ok",
        "baseline_ready": false,
        "drifted_asset_count": 0,
        "drifted_assets": [],
        "raw_status": {"baseline_ready": false, "assets": {}}
      }
    }
  ]
}
```

**4. Flag on + no drift — still a no-op (`reseed_attempted: false`):**

```bash
PRISM_DAGSTER_DRIFT_RESEED=1 python -m prism_orchestration --select scenario_drift_reseed
```

```json
{
  "success": true,
  "config": {"drift_reseed_enabled": true},
  "materializations": [
    {
      "asset": "scenario_drift_reseed",
      "metadata": {
        "status": "skipped",
        "reason": "no_drift_detected",
        "baseline_ready": false,
        "reseed_attempted": false
      }
    }
  ]
}
```

**5. Flag on + drifted features → real scenario-engine reset with `drift_signature` weights (Compose `scenario-engine` on `:9107`; drift status injected to isolate the edge):**

```json
{
  "success": true,
  "metadata": {
    "status": "ok",
    "reseed_attempted": true,
    "scenario_id": "scn_drift_reseed_17",
    "seed": 17,
    "weights": {
      "clean": 0.0,
      "sensor_corrupt": 0.0,
      "contract_violation": 0.0,
      "cv_low_confidence": 0.0,
      "cv_high_confidence": 0.0,
      "drift_signature": 1.0,
      "stalled_source": 0.0
    },
    "ticks_pulled": 5,
    "outcomes": [
      "drift_signature",
      "drift_signature",
      "drift_signature",
      "drift_signature",
      "drift_signature"
    ],
    "drifted_assets": [
      {
        "asset_id": "PRISM-AST-001",
        "group": "telemetry_numeric",
        "drifted_feature_count": 3
      }
    ]
  }
}
```

**6. Optional Compose UI:**

```bash
docker compose --profile dagster up -d --build orchestration
curl -sS -o /dev/null -w '%{http_code}\n' http://127.0.0.1:9112/
# → 200
```

## How to verify yourself

```bash
pip install -e lakehouse -e orchestration -e scenario-engine -e drift-monitor
# Phase 17 unit tests:
pytest -q tests/unit/test_orchestration.py
# → 8 passed

# Full suite:
pytest -q tests/unit
# → 135 passed

make phase17-check   # lint + full unit suite

# Flag-off no-op (must show reason=flag_off):
PRISM_DAGSTER_DRIFT_RESEED=0 python -m prism_orchestration --select scenario_drift_reseed

# Optional UI (needs Docker):
docker compose --profile dagster up -d --build orchestration
open http://127.0.0.1:9112
```

## Deferred (unchanged from the release plan)

| Item | To |
|------|-----|
| Promote Phase 14 YAML trip rules to real OPA/Rego policies | Phase 18 |
| Golden-path e2e extended to a full chaos scenario; cut v1.2.0 | Phase 19 |

## CI

Final concluded, green run on `2b77e72`: [CI run 30841381064](https://github.com/hamidmatiny/PRISM/actions/runs/30841381064) — Lint, Unit tests (135 passed), Cockpit typecheck/build, both Terraform matrix legs, the AWS terraform plan artifact, and the live Golden-path e2e all passed. ~5m 12s total.

## Stop

Phase 17 complete. **Do not start Phase 18** without explicit go-ahead.
