# Phase 14 — Per-source circuit breaker + incident-engine

## What changed

A new service, `incident-engine`, and wiring into `ingestion` and `cv-service` that answers the standing product requirement from this release: **if a source needs human action, stop that source — not the whole pipeline.** Conceptually adapted from Argus's incident-engine (closed → open → half_open FSM), reimplemented in Python against PRISM's own event vocabulary, not a port of Argus's Go code or its AV-specific trip conditions.

- **`incident-engine/` (new service, port 9108).** One `AssetBreaker` per `asset_id`, independent of every other asset's state — the isolation is the entire point. `fsm.py` holds the state machine; `store.py` is the FSM driver (`record_observation`) plus incident lifecycle (`acknowledge`, `resolve`); `journal.py` is a permanent, append-only audit trail (never truncated — every transition is kept, unlike scenario-engine's per-run journal); `webhook.py` is a local, testable notification sink (`POST /v1/webhook-test/receive` over loopback, falling back to a direct file append if the HTTP round-trip itself fails, so a webhook problem can never lose an alert).
- **Trip policies (`trip_policies.py` + packaged `default_policies.yaml`, declarative for now — real OPA/Rego is Phase 18):**
  - `quarantine_rate`: rolling window of the last 5 per-asset ingestion outcomes, trips at >15%.
  - `consecutive_qa_failures`: ≥3 consecutive review-routed (not published) cv-service findings for one asset, reset on any published finding.
  - `drifted_features`: ≥2 drifted features — intentionally dormant/no-op until Phase 16 builds the drift-monitor that would ever emit a `drift` observation. This is deliberate scope, not an oversight (ADR-005: don't fabricate readiness for a signal source that doesn't exist yet); it's still fully wired and unit-tested (`test_drifted_features_policy_is_dormant_but_wired`) so Phase 16 only has to start emitting the observation, not touch the FSM.
- **Half-open probe semantics.** After `cooldown_seconds` elapses on an open breaker, the *next single observation* is the probe — pass/fail is decided by that one observation alone (`ingestion_accepted` / `qa_pass` = pass; `ingestion_quarantined` / `qa_fail` = fail), not by re-blending it into the same rolling window that caused the trip. A window that's `[quarantined, quarantined, quarantined, quarantined, accepted]` is still an 80% rate — if probe pass/fail reused that window, one good observation could never clear a still-mostly-bad history. A caught-and-fixed design bug during this phase's build, not a reported one (see `docs/phases/README.md`'s note on self-review).
- **Retrip while open never mints a duplicate incident.** `store._refresh_incident` only creates a new `incident_id` if the breaker doesn't already have one open; otherwise it bumps `trip_count` and refreshes `trigger`/`last_transition_at` on the existing incident. An asset that keeps failing doesn't spam the incident list — it's still the one incident, with a rising trip count.
- **`ingestion` wiring (`incident_client.py`, `config.py`, `pipeline.py`):** every accept/reject decision fires a best-effort `report_observation(kind="ingestion_accepted" | "ingestion_quarantined")` to incident-engine. Best-effort means: incident-engine being down or slow never blocks or slows ingestion — failures are swallowed via `logger.debug`.
- **`cv-service` wiring (new `incident_client.py`, `pipeline.py`):** before the publish-vs-review decision, `breaker_is_open(incident_engine_url, asset_id)` is checked once per `detect_image()` call (not once per detection — a frame's findings share one source-health verdict). If the asset's breaker is open, **every finding from that asset is routed to review regardless of confidence** — this is the literal, direct implementation of "pause the source, not the whole process": findings keep flowing, humans just have to look at all of them until the source recovers. Every decision (published or reviewed) also reports `qa_pass`/`qa_fail` back to incident-engine, feeding the `consecutive_qa_failures` policy. incident-engine being unreachable fails open (treated as closed/healthy) — a dead incident-engine degrades detection to "no forced review," never blocks it.
- **`docker-compose.yml`:** new `incident-engine` service block (port 9108, same healthcheck pattern as scenario-engine), `PRISM_INCIDENT_ENGINE_URL` env + `depends_on` added to `ingestion` and `cv-service`.
- **`.github/workflows/ci.yml`:** `pip install -e incident-engine` added to both the `test` and `e2e` job install lists (required — otherwise CI can't import the new package at all); `pyyaml` added to the `e2e` job's install line (incident-engine's policy loader needs it; the `test` job already had it from Phase 1).
- **`Makefile`:** `setup` target installs `incident-engine` editable alongside the others; new `phase14-check` target + help text.
- **`cv-service/pyproject.toml`:** added `httpx>=0.27` as a real (not just dev) dependency — `incident_client.py` needs it at runtime, it was previously only present in `dev` extras.

## The concrete gap this closes

Before this phase, PRISM had no mechanism to isolate a misbehaving asset. A source producing garbage indefinitely would either quietly fill the DLQ forever with no signal anyone should look at it, or (worse, if a human decided to "fix" it by disabling ingestion generally) take every *other, healthy* asset's data down with it. Now: a specific asset's problem stays a specific asset's problem — its breaker opens, its cv-service findings get force-routed to review, and every other asset keeps flowing untouched. This is verified two ways below: 11 unit tests against synthetic observations (fast, deterministic, exercise every FSM edge case including half-open probe semantics and retrip-refresh), and one real multi-process live run (slow, real HTTP, real scenario-engine randomness) proving the isolation actually holds under real conditions, not just in a mocked FSM.

## Live proof — real scenario-engine + real ingestion + real incident-engine, not mocks, seed 42

Three real processes (`uvicorn`, no mocks) were started and driven together in a single sandbox session: `scenario-engine` (seed 42, 3 assets: `PRISM-AST-001/002/003`), `ingestion` (`PRISM_SOURCE_MODE=scenario`, pulling real events from scenario-engine over HTTP, reporting every accept/reject to incident-engine), and `incident-engine` itself. `GET /breakers` was polled every 0.2s while ingestion ran at 1 event/sec.

Because the outcome sequence is seed-deterministic and assets are served round-robin, `PRISM-AST-001`'s 5-observation window fills (and trips, given a real `quarantine_rate=0.2 > 0.15`) one tick before `PRISM-AST-002`'s and two before `PRISM-AST-003`'s — this is what created the window this proof captures, not a scripted shortcut. Actual captured response:

```json
{
  "count": 3,
  "breakers": [
    {
      "asset_id": "PRISM-AST-001",
      "state": "open",
      "incident_id": "inc_db3e76030722",
      "trip_reason": "quarantine_rate",
      "quarantine_rate": 0.2,
      "consecutive_qa_failures": 0,
      "drifted_feature_count": 0,
      "opened_at": "2026-08-02T19:36:59.718418Z",
      "last_transition_at": "2026-08-02T19:36:59.718418Z"
    },
    {
      "asset_id": "PRISM-AST-002",
      "state": "closed",
      "incident_id": null,
      "trip_reason": null,
      "quarantine_rate": null,
      "consecutive_qa_failures": 0,
      "drifted_feature_count": 0,
      "opened_at": null,
      "last_transition_at": "2026-08-02T19:36:48.678927Z"
    },
    {
      "asset_id": "PRISM-AST-003",
      "state": "closed",
      "incident_id": null,
      "trip_reason": null,
      "quarantine_rate": null,
      "consecutive_qa_failures": 0,
      "drifted_feature_count": 0,
      "opened_at": null,
      "last_transition_at": "2026-08-02T19:36:49.683194Z"
    }
  ]
}
```

`GET /v1/journal` corroborates the exact sequence that caused it — `PRISM-AST-001` accumulated one `ingestion_quarantined` inside its rolling window of 5, crossed the 15% threshold on its next observation, and the engine opened a real incident (`inc_db3e76030722`) and journaled the `closed → open` transition in the same request:

```json
{"asset_id": "PRISM-AST-001", "at": "...59.718315Z", "detail": {"kind": "ingestion_accepted"}, "event": "observation"},
{"asset_id": "PRISM-AST-001", "at": "...59.718441Z", "detail": {"incident_id": "inc_db3e76030722", "trigger": "quarantine_rate"}, "event": "incident_opened"},
{"asset_id": "PRISM-AST-001", "at": "...59.823210Z", "detail": {"from": "closed", "reason": "quarantine_rate", "to": "open"}, "event": "breaker_transition"}
```

`GET /incidents` at that same moment shows exactly one open incident, for `PRISM-AST-001` only:

```json
{"count": 1, "incidents": [{"incident_id": "inc_db3e76030722", "asset_id": "PRISM-AST-001", "trigger": "quarantine_rate", "status": "open", "trip_count": 1, ...}]}
```

## Unit tests (11 new, all passing)

`tests/unit/test_incident_engine.py`, run against a tight test-only policy set (`window=3`, `cooldown=0.3s`) so FSM edge cases don't need multi-second sleeps: per-asset isolation under `quarantine_rate`, `consecutive_qa_failures` tripping and resetting on any pass, retrip-while-open refreshing the same `incident_id` instead of minting a new one, cooldown → good probe → auto-resolve, cooldown → bad probe → retrip (same incident), manual acknowledge/resolve, unknown-incident 404, unknown-observation-kind 400, webhook inbox receiving `incident_opened`, journal recording every transition, and the dormant-but-wired `drifted_features` policy.

Full repo regression: **105 passed, 2 skipped** (`tests/unit`, same 2 pre-existing skips as Phase 13 — one is the local-JVM-optional Spark test, unrelated to this phase). No regressions from wiring `report_observation`/`breaker_is_open`/`report_qa_observation` into the hot paths of `ingestion` and `cv-service` — both packages' own test files stayed at the same pass counts (12 and 8 respectively) and, after fixing a performance regression below, at the same speed.

## A bug caught and fixed during the build, not reported by anyone

Wiring `ingestion/pipeline.py` to call `report_observation()` on every accept/reject slowed `tests/unit/test_ingestion.py` from near-instant to 4.15s for 12 tests. Traced to `httpx.Client()` re-parsing `https_proxy`/`no_proxy` environment variables on every construction — real, measurable overhead at the call rate a hot path produces. Fixed by rewriting `incident_client.py` (and `cv-service`'s equivalent) to use a module-level cached client with `trust_env=False` explicitly set — also more correct behavior on its own merits, since these are local sidecar calls that should never go through a proxy. Confirmed: 12 tests back to 0.40s.

## Why this is Cursor's Phase 14, done differently

Same situation as Phase 13: Cursor is still at its monthly usage limit. With the user's explicit "move forward, same tactics" authorization, this phase was built directly against the real repository in the same isolated sandbox as Phase 13 — no Docker, no outbound access to GitHub release assets, Python 3.12 not obtainable locally. The live proof above ran on Python 3.10 with the same disclosed stdlib compatibility shim used in Phase 13 (`datetime.UTC`, `typing.Self`, `enum.StrEnum` backported for local verification only, never shipped). **The Docker demo run in "Verify it yourself" below is the step you should run yourself as the authoritative confirmation.**

## CI

Final concluded, green run on `9c0d42f`: [CI run
30768843764](https://github.com/hamidmatiny/PRISM/actions/runs/30768843764) —
Lint (7s), Unit tests (2m 43s, 105 passed/2 skipped), Cockpit build (19s),
both Terraform matrix legs, the AWS terraform plan artifact, and the live
Golden-path e2e (2m 9s) all passed. Total 5m 4s. Only annotations were
GitHub's own Node.js 20 deprecation notices on its runner actions — nothing
related to this phase's changes. This run wasn't reported until it showed a
concluded `Status Success`, not while any job was still in progress. First
push attempt (with an earlier, more narrowly-scoped PAT) was rejected before
even reaching CI: GitHub refused to accept a push modifying
`.github/workflows/ci.yml` without the token's `workflow` scope. Resolved by
the user issuing a new token with that scope added; no code change was
needed, this was a push-permission issue only.

## Correction (found during the user's own real-machine test run)

The first version of this doc's "Verify it yourself" section claimed
`make demo` runs ingestion in scenario mode and a breaker would trip within
15-20 seconds of natural traffic. That was wrong, and wasn't caught until
the user actually ran it: `docker-compose.demo.yml` sets
`PRISM_FAILURE_RATE=0` for ingestion specifically so the demo's golden path
(approve -> gold) stays deterministic. `make demo` never was going to trip a
breaker on its own -- the user's real run confirmed this directly (30+
`ingestion_accepted` observations, zero `ingestion_quarantined`, over about
90 seconds). Their manual `POST /v1/observations` workaround is what
actually proved the mechanism, and is now Option A below. Corrected below
and in the instructions given directly to the user.

## Verify it yourself

```bash
git pull
python3.12 -m venv .venv && source .venv/bin/activate   # real 3.12, not a substitute
make setup
make lint
# expect: "All checks passed!" / "N files already formatted"

make test
# expect: 105 passed (was 94 before this phase), 2 skipped.
pytest -q tests/unit/test_incident_engine.py -v
# expect: 11 passed

# Live proof, on your machine, against the real Docker stack:
make demo
curl -s http://127.0.0.1:9108/health | python3 -m json.tool
# expect assets_tracked / open_breakers / policies in the response

# IMPORTANT: docker-compose.demo.yml sets PRISM_FAILURE_RATE=0 for ingestion
# specifically so the demo's golden path (approve -> gold) stays deterministic.
# `make demo` will NOT trip a breaker on its own -- there is no corruption for
# it to react to. An earlier draft of this doc said otherwise; that was wrong,
# caught only after a real run showed 30+ "ingestion_accepted" observations and
# zero trips. Two correct ways to actually see a trip, both real, not mocked:

# Option A -- force it via the API directly against the demo stack (fastest,
# and exactly what proves the mechanism independent of ingestion's own logic):
for i in 1 2 3 4 5; do
  curl -s -X POST http://127.0.0.1:9108/v1/observations \
    -H 'content-type: application/json' \
    -d '{"asset_id": "PRISM-AST-002", "kind": "ingestion_quarantined"}' > /dev/null
done
curl -s http://127.0.0.1:9108/breakers/PRISM-AST-002 | python3 -m json.tool
# expect "state": "open", a real quarantine_rate and incident_id; the other two
# assets' breakers are untouched -- check with:
curl -s http://127.0.0.1:9108/breakers | python3 -m json.tool

# Option B -- reproduce the actual seed-42 scenario-engine live proof from this
# doc, with real ingestion-generated corruption (recreates the ingestion container
# with the env override, same pattern documented in PHASE_12_COMPLETION.md):
PRISM_SOURCE_MODE=scenario PRISM_FAILURE_RATE=0.05 docker compose up -d --build scenario-engine ingestion
# poll during/after (macOS has no `watch` by default -- this loop works everywhere):
for i in $(seq 1 15); do curl -s http://127.0.0.1:9108/breakers | python3 -m json.tool; sleep 2; done
# to go back to the deterministic demo mode afterward:
docker compose up -d --build ingestion

curl -s http://127.0.0.1:9108/incidents | python3 -m json.tool
curl -s "http://127.0.0.1:9108/v1/journal?limit=30" | python3 -m json.tool

make e2e
make down
```

To see the forced-review behavior directly (cv-service side), with
`PRISM-AST-002`'s breaker open from Option A above:

```bash
# any subsequent cv-service finding for PRISM-AST-002 is now forced to review
# regardless of confidence -- check .data/cv-review-queue/pending/ or cv-service logs.
```

## Paths to open if you distrust this summary

- `incident-engine/src/prism_incident_engine/fsm.py` — the `AssetBreaker` state machine itself.
- `incident-engine/src/prism_incident_engine/store.py` — `record_observation`, especially the half-open probe branch and `_refresh_incident`'s no-duplicate-incident logic.
- `incident-engine/src/prism_incident_engine/trip_policies.py` + `policies/default_policies.yaml` — the actual thresholds.
- `tests/unit/test_incident_engine.py` — all 11 Phase 14 tests, especially `test_retrip_while_open_refreshes_same_incident` and `test_cooldown_then_bad_probe_retrips`.
- `ingestion/src/prism_ingestion/incident_client.py`, `cv-service/src/prism_cv_service/incident_client.py` — the best-effort/fail-open reporting clients.
- `cv-service/src/prism_cv_service/pipeline.py` — the `forced_review` check, one call per frame not per detection.
- `docker-compose.yml` — `incident-engine` service block, and the `PRISM_INCIDENT_ENGINE_URL` wiring on `ingestion`/`cv-service`.
