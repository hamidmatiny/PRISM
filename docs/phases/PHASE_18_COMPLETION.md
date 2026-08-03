# Phase 18 completion — OPA/Rego trip policy maturity

**Date:** 2026-08-03
**Status:** Complete
**Track:** v1.2.0 (Phases 16–19)

## What shipped

- **Rego is the trip source of truth** under `incident-engine/policies/rego/`:
  - `quarantine_rate.rego` — window ≥ 5 and quarantined/window > 0.15
  - `consecutive_failures.rego` — streak ≥ 3
  - `drift_count.rego` — drifted feature count ≥ 2
  - `escalation.rego` — PRISM-specific severity / notify routing for the mock webhook
  - `trip.rego` — aggregates the three trip packages in Phase 14's priority order
  - Matching `*_test.rego` files — **18/18** pass via `opa test` with **zero Python involvement**
- **`incident-engine` queries OPA for every trip decision** (`fsm.AssetBreaker.tripped_policy` → `PolicyEngine.evaluate_trip`). Threshold comparisons were removed from Python; YAML (`default_policies.yaml`) only sizes the FSM rolling window + cooldown so the buffer matches Rego's `window_min`.
- **Local OPA only (ADR-001):** Compose service `opa` (`openpolicyagent/opa:1.4.2`) on host **:9113**; `incident-engine` talks HTTP via `PRISM_OPA_URL`. Unit tests / no-sidecar path uses `opa eval` against the same policy directory. Justification: the open-source OPA binary is free, runs entirely locally, and is the same engine that executes `opa test` — no SaaS, no new paid dependency, and policy logic stays reviewable as `.rego` diffs.
- **Fail-open when OPA is unreachable (ADR-005):** no trip is invented; `/health` reports `policy_engine.ready: false` / error metadata on the breaker. **No silent fallback** to the old YAML threshold comparisons.
- **Escalation route** from Rego is attached to `incident_opened` journal + mock webhook payloads.
- **CI:** installs OPA 1.4.2, runs `opa test incident-engine/policies/rego -v` before pytest.
- **Doc hygiene (separate prior commit `bfca609`):** README Status rows 16–17, monorepo tree (`drift-monitor/`, `orchestration/`), RELEASE_PLAN checklist dup removed, foundation guards for README Status/tree staleness.

## Live proof — real commands, pasted output

**1. Rego unit tests (policy logic independent of incident-engine):**

```bash
opa test incident-engine/policies/rego -v
# → PASS: 18/18
```

**2. Compose OPA + incident-engine — health shows Rego as source of truth, HTTP mode ready:**

```bash
docker compose up -d --build opa incident-engine
curl -sS http://127.0.0.1:9113/health
# → {}
curl -sS http://127.0.0.1:9108/health
```

```json
{
  "status": "ok",
  "service": "incident-engine",
  "version": "0.18.0",
  "policy_engine": {
    "ready": true,
    "mode": "http",
    "policy_dir": "/policies/rego",
    "source_of_truth": "rego"
  },
  "fsm": {
    "quarantine_rate_window": 5,
    "cooldown_seconds": 8.0
  }
}
```

**3. Five quarantined observations → breaker opens with `trip_reason=quarantine_rate` (decision from OPA HTTP):**

```bash
for i in 1 2 3 4 5; do
  curl -sS -X POST http://127.0.0.1:9108/v1/observations \
    -H 'content-type: application/json' \
    -d '{"asset_id":"PRISM-AST-018b","kind":"ingestion_quarantined"}'
  echo
done | tail -1
```

```json
{
  "asset_id": "PRISM-AST-018b",
  "state": "open",
  "incident_id": "inc_be5ebfe1e5a9",
  "trip_reason": "quarantine_rate",
  "quarantine_rate": 1.0,
  "policy_engine_error": null
}
```

**4. Mock webhook carries Rego escalation routing:**

```json
{
  "event": "incident_opened",
  "asset_id": "PRISM-AST-018",
  "trigger": "quarantine_rate",
  "escalation": {
    "channel": "mock_webhook",
    "severity": "medium",
    "notify": ["ops"],
    "policy": "quarantine_rate",
    "policy_engine_ready": true
  }
}
```

**5. Direct OPA Data API (same bundle the service uses):**

```bash
curl -sS http://127.0.0.1:9113/v1/data/prism/trip/decision \
  -H 'content-type: application/json' \
  -d '{"input":{"quarantine_window":[true,true,true,true,true],"consecutive_qa_failures":0,"drifted_feature_count":0}}'
```

```json
{
  "result": {
    "policy_engine": "opa",
    "reason": "quarantine_rate",
    "trip": true
  }
}
```

**6. Fail-open when policy engine unavailable — five quarantines do not trip; error recorded:**

```json
{
  "asset_id": "X",
  "state": "closed",
  "trip_reason": null,
  "quarantine_rate": 1.0,
  "policy_engine_error": "policy_engine_unavailable"
}
```

## How to verify yourself

```bash
# 0) OPA binary (once):
# macOS arm64 example — or use the Compose opa service only
curl -fsSL -o .venv/bin/opa \
  https://openpolicyagent.org/downloads/v1.4.2/opa_darwin_arm64_static
chmod +x .venv/bin/opa
export PATH="$PWD/.venv/bin:$PATH"

# 1) Rego tests only — expect PASS: 18/18
opa test incident-engine/policies/rego -v

# 2) Python unit suite (includes fail-open + Rego-backed trips)
pip install -e incident-engine
pytest -q tests/unit/test_incident_engine.py
# → 13 passed

# 3) Full suite
pytest -q tests/unit
# → 139 passed

make phase18-check   # lint + opa test + full unit suite

# 4) Live Compose path
docker compose up -d --build opa incident-engine
curl -sS http://127.0.0.1:9108/health | python3 -m json.tool
# expect policy_engine.ready=true, source_of_truth=rego, mode=http

for i in 1 2 3 4 5; do
  curl -sS -X POST http://127.0.0.1:9108/v1/observations \
    -H 'content-type: application/json' \
    -d '{"asset_id":"PRISM-AST-DEMO","kind":"ingestion_quarantined"}' | python3 -m json.tool
done
# final state.state should be "open", trip_reason "quarantine_rate"
```

## Deferred (unchanged from the release plan)

| Item | To |
|------|-----|
| Golden-path e2e extended to a full chaos scenario; cut v1.2.0; case study | Phase 19 |

## CI

Final concluded, green run on `a070b6c`: [CI run 30844247827](https://github.com/hamidmatiny/PRISM/actions/runs/30844247827) — Lint, Unit tests (including `opa test` 18/18), Cockpit typecheck/build, both Terraform matrix legs, the AWS terraform plan artifact, and the live Golden-path e2e (which built `opa` + rebuilt `incident-engine` for real) all passed. 5m 22s total.

## Stop

Phase 18 complete. **Do not start Phase 19** without explicit go-ahead.
