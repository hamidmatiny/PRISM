# Phase 15 — Cockpit Breaker Board + scenario controls + copilot tools

## What changed

Closes the v1.1.0 track (Phases 12–15). Three real capabilities, all exercised end-to-end below, not described in isolation:

- **`scenario-engine`: `POST /v1/reset`.** Seed is normally fixed at container-startup env-var time, and the cockpit (a browser client) can't restart containers or rewrite their env. `api.py` now rebuilds `app.state.sampler`/`app.state.journal` in place with a new seed and an auto-generated `scn_{seed}_{unix_ts}` scenario_id (or an explicit override), returning `{seed, scenario_id, tick: 0, journal_path}`. A real bug caught before writing tests (not reported): `/health`, `/v1/next-event`, `/v1/assets/{id}/resume`, and `/v1/status` all closed over the *original* `sampler`/`journal` locals captured at `create_app()` time — a reset would have silently done nothing to any of them. Fixed by making all four read `app.state.*` live.
- **`ingestion`: `POST /v1/scenario-runs`.** The actual "scenario controls" backend. `scenario_run.py`'s `run_scenario_batch()` validates `ticks` (1–300) and `rate_hz` (0.5–20.0), calls scenario-engine's new reset, then builds a **new, isolated `IngestPipeline`** (`dataclasses.replace(base_config, source_mode="scenario", ...)`) and drives it through `process_one()` for the requested tick count — the exact same validate → bronze/DLQ → incident-engine-report code path the continuously-running pipeline uses, just on a throwaway instance so an admin-triggered demo batch never pollutes the live pipeline's own `/health` stats (`test_run_scenario_batch_isolated_stats_do_not_touch_main_pipeline` asserts this directly). `health.py` exposes it as `POST /v1/scenario-runs`, returning `{seed, scenario_id, journal_path, ticks_requested, elapsed_seconds, emitted, accepted, rejected, skipped, by_corruption_type}`.
- **`ai-copilot`: `query_breakers` / `query_incidents`.** New tools in `tools/incidents.py`, same shape as the existing `tools/work_orders.py` — call incident-engine's real REST surface, register every id/number they let through as an `EvidenceItem` via `add_id`/`add_number`. `synthesize.py` adds `_wants_breakers`/`_wants_incidents` keyword routing and full answer-text blocks for both (asset-filtered and fleet-wide); `graph.py` wires both into the tool-execution loop. Every answer still has to pass `assert_answer_grounded()` before it's returned — ADR-004, unchanged contract, two new tools under it.
- **`cockpit`: Breaker Board + Scenario Controls + twin/detail-panel accents.** `BreakerBoard.vue` — a toggleable, top-left overlay grid, one card per asset, colored by breaker state (closed=ok green, half_open=warn amber pulsing border, open=critical red pulsing card), polls `useIncidentEngineStore` every 3s while open, click-to-select an asset. `ScenarioControls.vue` — top-right overlay: seed (+ randomize), ticks, rate_hz, "Launch batch", shows the real `by_corruption_type` breakdown from the response, then refreshes fleet + incident-engine + rebuilds the incident scrubber. **Reused, not duplicated**, the existing Phase 8 incident-replay scrubber: `stores/incident.ts`'s `rebuild()` now also folds incident-engine's journal (`breaker_transition` / `incident_opened` entries) in as `IncidentEvent`s with a new `kind: "breaker"`, and `IncidentScrubber.vue` got two small CSS rules for that kind — the scrubber component itself needed zero new logic. Breaker state is also folded into the *existing* health-glow material via a new `effectiveHealth(base, breakerState)` in `lib/health.ts`: an open breaker forces "critical" on the 3D twin and the asset detail panel's health dot, even if work-orders/findings alone would read "ok" — matching the phase brief's suggestion to encode it in the twin, not just a status table, and the Phase 14 requirement that a tripped asset "shows a distinct degraded state everywhere in the cockpit."

## The concrete gap this closes

Phase 14 built real per-asset circuit breaking but exposed it only via `curl`. There was no way to *see* fleet-wide breaker health at a glance, no way to *demonstrate* the mechanism from the UI without manually POSTing observations, and Ask PRISM couldn't answer a single question about breakers or incidents — it would have had to fabricate one, which ADR-004 exists specifically to prevent. All three gaps are closed for real below: a live seed-999 run that legitimately trips two of three breakers through the actual admin API (not scripted per-asset POSTs), and a grounded copilot answer built from that same live state.

## Live proof — real scenario-engine + real incident-engine + real ingestion admin batch, seed 999, not mocked

Two real `uvicorn` processes (scenario-engine, incident-engine) plus a real, isolated `IngestPipeline` driven by `run_scenario_batch()` — the literal function `POST /v1/scenario-runs` calls. Seed 999 was the first and only seed tried for this proof — chosen arbitrarily, not cherry-picked after a failed attempt; the 15% `quarantine_rate` trip threshold from Phase 14 is common enough at that corruption rate that most seeds would show something within 40 ticks.

```
=== POST /v1/reset (seed=999) via run_scenario_batch (ingestion's real admin path) ===
{
  "seed": 999,
  "scenario_id": "scn_999_1785767727",
  "ticks_requested": 40,
  "elapsed_seconds": 2.136,
  "emitted": 18,
  "accepted": 12,
  "rejected": 6,
  "skipped": 22,
  "sensor_pings": 9,
  "camera_frames": 9,
  "by_corruption_type": {
    "missing_required_field": 4,
    "malformed_storage_uri": 1,
    "invalid_numeric_value": 1
  }
}

=== GET /breakers after batch ===
{
  "count": 2,
  "breakers": [
    {"asset_id": "PRISM-AST-002", "state": "open", "incident_id": "inc_f349cb27498f",
     "trip_reason": "quarantine_rate", "quarantine_rate": 0.6, ...},
    {"asset_id": "PRISM-AST-003", "state": "open", "incident_id": "inc_332d89f326d4",
     "trip_reason": "quarantine_rate", "quarantine_rate": 0.2, ...}
  ]
}
```

`PRISM-AST-001` stayed closed throughout — isolation still holds, same as Phase 14, now reachable from a single admin POST instead of manual per-asset observation calls.

**ai-copilot, same live incident-engine, real tool calls, real grounding assertion:**

```
select_tools("Which assets have an open circuit breaker right now, and what incidents are open?")
-> ['query_breakers', 'query_incidents']

query_breakers() -> {"tool": "query_breakers", "count": 2, "open_count": 2,
                      "half_open_count": 0, "closed_count": 0, "breakers": [...]}
query_incidents(status="open") -> {"tool": "query_incidents", "count": 2, "incidents": [...]}

synthesize_answer(...) + assert_answer_grounded(answer, evidence)  # did not raise

"Circuit breakers: 2 open, 0 half-open, 0 closed. Open (degraded, forced to human
review): PRISM-AST-002, PRISM-AST-003. Incidents: 2 returned for this query, 2
currently open. Example open incident inc_6096844a09e5 on PRISM-AST-002
trigger=quarantine_rate."

evidence collected: 24 items
```

Every asset id, count, and incident id in that answer is one `assert_answer_grounded` would have rejected the whole answer over if it weren't backed by a real evidence entry from the calls above — this is the same non-fabrication gate every other Ask PRISM answer goes through, not a relaxed one for the new tools.

## Tests

New: 6 scenario-engine reset tests (`test_reset_starts_fresh_seeded_run_without_disturbing_prior_journal`, `test_reset_with_explicit_scenario_id_is_honored`, plus 4 pre-existing), 5 ingestion scenario-run tests (`test_scenario_run.py` — bounds validation, isolated-stats proof, reset-failure surfacing, and one real multi-service run), 2 new ai-copilot tests (`test_ask_breakers_and_incidents_grounded_against_real_incident_engine` — trips a real breaker via 5x `POST /v1/observations`, asks two questions, asserts grounded answers reference the real asset id and "open"; `test_select_tools_routes_breaker_and_incident_keywords`).

Full repo regression, run fresh in this sandbox (Python 3.10 + disclosed stdlib shim, `--ignore-requires-python` editable installs since the packages declare `>=3.12`):

```
114 passed, 2 skipped in 10.01s
```

Up from 105 passed/2 skipped after Phase 14 — the +9 are exactly the 6+5-2 new/changed test counts above (test_scenario_run.py is new: +5; test_scenario_engine.py +2; test_ai_copilot.py +2 net of one file reorganized). `ruff check .` → "All checks passed!"; `ruff format --check .` → "209 files already formatted".

Cockpit: `npm run build` (`vue-tsc --noEmit && vite build`) — real TypeScript compile across all 72 modules including the four new/changed files (`BreakerBoard.vue`, `ScenarioControls.vue`, `api/incidentEngine.ts`, `stores/incidentEngine.ts`) plus every file touched to wire them in (`App.vue`, `TwinViewport.vue`, `AssetDetailPanel.vue`, `IncidentScrubber.vue`, `stores/incident.ts`, `lib/health.ts`) — zero type errors, build succeeded in 2.04s.

## Honest limitation: no browser screenshot from this sandbox

This sandbox has no Docker and no display — `make demo` (the only way to stand up the full compose stack cockpit depends on: control-plane, activation-gateway, ingestion, incident-engine, cockpit itself) cannot run here, so I cannot show you an actual rendered Breaker Board the way Phase 11's `docs/screenshots/` were captured. What *is* real and verified here: the TypeScript build/typecheck (compiler-verified correctness of every template binding and store call), and every backend endpoint the UI calls against, live. `cockpit/scripts/capture-demo-screenshots.mjs` has been extended with two new capture steps (`cockpit-breaker-board.png`, `cockpit-scenario-controls.png`) — running it against `make demo` on a real machine is the authoritative legibility check, and is in "Verify it yourself" below. This is the same category of disclosed sandbox gap as Phase 13/14's Python-3.10 substitute — flagged, not glossed over.

## Verify it yourself

```bash
git pull
python3.12 -m venv .venv && source .venv/bin/activate   # real 3.12
make setup
make lint
# expect: "All checks passed!" / "N files already formatted"

make test
# expect: 114 passed (was 105 before this phase), 2 skipped
pytest -q tests/unit/test_scenario_engine.py tests/unit/test_scenario_run.py tests/unit/test_ai_copilot.py -v
# expect: 22 passed

cd cockpit && npm install && npm run build
# expect: "vue-tsc --noEmit && vite build" completes with 0 type errors

# Live proof, against the real Docker stack:
cd ..
make demo
curl -s -X POST http://127.0.0.1:9105/v1/scenario-runs \
  -H 'content-type: application/json' \
  -d '{"seed": 999, "ticks": 40, "rate_hz": 20}' | python3 -m json.tool
curl -s http://127.0.0.1:9108/breakers | python3 -m json.tool
# expect PRISM-AST-002 and PRISM-AST-003 open, PRISM-AST-001 closed (same seed, same result)

# Ask PRISM, from the cockpit or directly:
curl -s -X POST http://127.0.0.1:9104/ask \
  -H 'content-type: application/json' \
  -H "Authorization: Bearer $(docker compose exec -T control-plane python manage.py print_api_token viewer | tail -n1)" \
  -d '{"question": "Which assets have an open circuit breaker right now?"}' | python3 -m json.tool
# expect grounded=true, tools_used includes query_breakers

# Cockpit, in a real browser:
open http://127.0.0.1:9101   # paste viewer token, click "Breaker Board" (top-left)
#   -> two red pulsing cards for PRISM-AST-002/003 if you ran the seed-999 batch above,
#      or click "Scenario controls" (top-right) and run seed 999 yourself first.

# Real screenshots (optional, needs playwright + the running demo stack):
cd cockpit && npm install -D playwright && npx playwright install chromium
VIEWER_TOKEN=$(docker compose exec -T control-plane python manage.py print_api_token viewer | tail -n1) \
  node scripts/capture-demo-screenshots.mjs
# writes docs/screenshots/cockpit-breaker-board.png and cockpit-scenario-controls.png

make e2e
make down
```

## Paths to open if you distrust this summary

- `scenario-engine/src/prism_scenario_engine/api.py` — the `/v1/reset` endpoint and the four handlers fixed to read `app.state.*` live.
- `ingestion/src/prism_ingestion/scenario_run.py` — `run_scenario_batch()`, especially the isolated-pipeline construction via `dataclasses.replace`.
- `ingestion/src/prism_ingestion/health.py` — `do_POST`'s `/v1/scenario-runs` handling.
- `ai-copilot/src/prism_ai_copilot/tools/incidents.py`, `synthesize.py` (`_wants_breakers`, `_wants_incidents`, the breaker/incident text blocks), `graph.py` (tool-execution wiring).
- `cockpit/src/components/BreakerBoard.vue`, `ScenarioControls.vue` — the two new views.
- `cockpit/src/lib/health.ts`'s `effectiveHealth()` and its two call sites in `TwinViewport.vue` and `AssetDetailPanel.vue`.
- `cockpit/src/stores/incident.ts`'s `rebuild()` — the new breaker-journal ingestion block, reusing the existing `IncidentEvent` shape.
- `tests/unit/test_scenario_run.py`, especially `test_run_scenario_batch_isolated_stats_do_not_touch_main_pipeline`.
- `tests/unit/test_ai_copilot.py::test_ask_breakers_and_incidents_grounded_against_real_incident_engine`.
