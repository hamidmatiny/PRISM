# Phase 12 completion — Scenario engine (seeded, audited chaos)

**Date:** 2026-08-02  
**Status:** Complete  
**Track:** v1.1.0 (Phases 12–15)

## What shipped

- [`scenario-engine/`](../../scenario-engine/) on host **`:9107`** — FastAPI, weighted outcomes, append-only JSONL audit journal under `$PRISM_DATA_ROOT/scenario/journal/`
- Outcomes: `clean`, `sensor_corrupt`, `contract_violation`, `cv_low_confidence`, `cv_high_confidence`, `drift_signature`, `stalled_source` (+ `POST /v1/assets/{id}/resume`)
- Every emit carries `synthetic_scenario: true` + `scenario_id` ([ADR-005](../adr/005-earned-evidence-policy.md))
- Ingestion `PRISM_SOURCE_MODE=live|scenario` + `PRISM_SCENARIO_URL` — scenario mode HTTP-pulls `GET /v1/next-event`; ingestion remains the contract / bronze / DLQ authority
- Telemetry schema optional fields: `synthetic_scenario`, `scenario_id`, `scenario_outcome`
- Compose service `scenario-engine`; docs/ports/Makefile `phase12-check`; CI `pip install -e scenario-engine`

## Deferred

| Item | To |
|------|-----|
| Two-layer Pydantic → Pandera DLQ enrichment | Phase 13 |
| Per-asset circuit breakers / incident-engine | Phase 14 |
| Cockpit Breaker Board + copilot tools | Phase 15 |

## How to verify

```bash
make phase12-check
# Seed replay (journals must be identical):
# see scenario-engine/README.md "Test it yourself"
PRISM_SOURCE_MODE=scenario docker compose up -d --build scenario-engine ingestion
curl -sS http://127.0.0.1:9107/health
curl -sS http://127.0.0.1:9105/health   # source_mode=scenario
```

## Proof (captured 2026-08-02)

### Seed replay — journals byte-identical

```text
diff /tmp/prism-scn-a/scenario/journal/scn_42.jsonl \
     /tmp/prism-scn-b/scenario/journal/scn_42.jsonl \
  && echo JOURNALS_IDENTICAL
# → JOURNALS_IDENTICAL
```

Journal line 1 (seed=42, 40 ticks):

```json
{"asset_id": "PRISM-AST-001", "emitted": true, "event_id": "frm_1fe7a90141c2", "kind": "camera_frame", "outcome": "cv_high_confidence", "scenario_id": "scn_42", "seed": 42, "tick": 1}
```

### Compose — scenario mode

`GET http://127.0.0.1:9107/health`:

```json
{"status": "ok", "service": "scenario-engine", "version": "0.12.0", "seed": 42, "scenario_id": "scn_42", "synthetic_scenario": true}
```

`GET http://127.0.0.1:9105/health` (excerpt):

```json
{"source_mode": "scenario", "scenario_url": "http://scenario-engine:9107", "stats": {"emitted": 26, "accepted": 20, "rejected": 5}}
```

Accepted bronze record carries synthetic labels:

```json
{"asset_id": "PRISM-AST-003", "synthetic_scenario": true, "scenario_id": "scn_42", "event_type": "camera_frame"}
```

DLQ records from corrupt outcomes retain labels (`sensor_corrupt`, `contract_violation`).

## Stop

Phase 12 complete. **Do not start Phase 13** without explicit go-ahead.
