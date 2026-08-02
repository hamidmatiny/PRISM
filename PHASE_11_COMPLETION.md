# Phase 11 completion — Productionization & demo

**Date:** 2026-08-02  
**Status:** Complete (final phase)

## What shipped

- **Golden-path e2e** (`tests/e2e/test_golden_path.py`): live compose chain  
  ingest → CV review queue → inspector approve → `cv_findings` gold →  
  `asset_daily_metrics` bump visible in **Redshift and Snowflake** mocks →  
  cockpit proxies → grounded **Ask PRISM** answer  
- **`make demo`** (`examples/demo/run_demo.sh` + `docker-compose.demo.yml` + seed):  
  full stack with realistic gold/assets/WOs in **under five minutes** (measured **16s** warm / rebuild-bound cold)  
- Finalized [ARCHITECTURE.md](ARCHITECTURE.md), four ADRs, [docs/DEMO_SCRIPT.md](docs/DEMO_SCRIPT.md)  
- Real cockpit screenshots under [docs/screenshots/](docs/screenshots/)  
- CI job `e2e` runs **after** lint + unit + cockpit + terraform + plan so every prior gate must be green first  
- Fix found by golden path: Ask PRISM synthesizer counted per-asset pending/WO rows without putting those counts in ADR-004 evidence (`synthesize.py`)

## Verified (local proof — re-run before you sign off)

| Check | Result |
|-------|--------|
| `make demo` | Ready in **16s** (&lt; 300s budget); printed viewer token |
| `PRISM_E2E=1 pytest -q tests/e2e -m e2e` | **1 passed** |
| `pytest -q tests/unit` | Green |
| Cockpit screenshots (PNG 1440×900) | Committed; show twin + Ask PRISM grounded answer |
| GitHub Actions for this commit | Linked after push |

Paths to open if you distrust the summary (learned from Phase 10):

- Rotation attachments: `infra/terraform/aws/modules/secrets/main.tf` (`aws_secretsmanager_secret_rotation`)  
- Golden path: `tests/e2e/test_golden_path.py`  
- Demo entrypoint: `examples/demo/run_demo.sh`  
- Screenshots: `docs/screenshots/*.png` (binary — open in viewer)

## Test it yourself

```bash
make demo
# open http://127.0.0.1:9101 — paste printed viewer token

PRISM_E2E=1 pytest -q tests/e2e -m e2e -vv

# Prior-phase gates simultaneously (no live compose):
make phase11-check

# Screenshots already committed; optional re-capture:
cd cockpit && npm ci && npx playwright install chromium
VIEWER_TOKEN=$(docker compose exec -T control-plane python manage.py print_api_token viewer | tail -n1) \
  node scripts/capture-demo-screenshots.mjs
```

## Explicit non-claims

- Warehouse “Redshift/Snowflake” in the golden path are the **local mock adapters** (`:9110`/`:9111`) behind the real activation contract — not paid cloud warehouses (ADR-001).  
- `make demo` cold builds depend on Docker image cache; the script still enforces a hard 300s deadline.  
- Screenshots are from a live local session; GPU/WebGPU availability varies by machine (WebGL fallback exists).

## Stop

Phase 11 is the last phase. No Phase 12.
