# Phase 16 completion — Drift detection with honest baseline gating

**Date:** 2026-08-03
**Status:** Complete
**Track:** v1.2.0 (Phases 16–19)

## What shipped

- **`drift-monitor/`** (new service, port **9109**) — sentinel-ray's drift math (`detector.py`: two-sample KS test on numeric features, centroid distance, KS test on vector norms), gated end-to-end by ADR-005's `baseline_ready` discipline. `tracker.py` is the per-`(asset_id, group)` state machine: real, non-synthetic observations accumulate until `PRISM_DRIFT_BASELINE_SAMPLES` (default 20) real samples exist, at which point the baseline freezes permanently and detection goes live; `store.py` orchestrates trackers and fire-and-forgets a `kind: "drift"` observation to incident-engine whenever a detection run finds `drifted_feature_count >= 1`.
- **Two feature groups**, matching the two real (non-fabricated) signal sources PRISM's pipeline actually produces:
  - `telemetry_numeric` — the numeric fields of a validated `SensorPing`. **`odometer_km` was deliberately excluded** (see "Bug caught during build" below).
  - `cv_geometry` — a real, low-dimensional feature vector computed from a genuine cv-service `CvFinding` (confidence, box width/height, aspect ratio, one-hot defect class).
- **Honest deviation from the release plan, documented, not hidden:** the release plan's lineage table describes sentinel-ray's math as including "embedding centroid distance" and "KS on embedding norms." PRISM's actual cv-service (`cv-service/src/prism_cv_service/detector.py`) is a bounding-box YOLO-style ONNX decoder with **no embedding head** — there is no deep embedding anywhere in this codebase to compare. Rather than fabricate one (the exact failure mode ADR-005 exists to block), `detector.py` runs the same centroid-distance and norm-KS math against the real `cv_geometry` feature vector described above, and every place it's surfaced — code comments, docstrings, API field names, this document — calls it a "feature vector," never an "embedding."
- **The baseline gate, concretely:** only `synthetic_scenario=false` observations ever count toward a real baseline (`baseline.py`) — scenario-engine's chaos events, including its own `drift_signature` outcome, are exactly the kind of synthetic data Argus's ADR-007 separate-sink rule says must never co-own a real reference. They're fully eligible for the **comparison window** once a real baseline exists (checking whether current traffic — chaos-test or real — has drifted away from an earned baseline is the entire point). Before a real baseline exists, a `ColdStartPlaceholder` (fabricated, standard-normal, explicitly labeled) is held only so `/health` and `/v1/status` have a non-null shape — it is never passed into `ks_2samp`, `centroid_distance`, or `ks_on_norms`; grep the package for `ColdStartPlaceholder` and it's read in exactly one place (`status()`), never in `observe()`'s detection branch.
- **incident-engine wiring:** this producer is exactly the one Phase 14 shipped dormant-but-wired — `record_drift(drifted_feature_count=...)` and the `drifted_features_threshold` policy check already existed, waiting for a real caller. No incident-engine code changed in this phase; `drift-monitor` is simply the first thing to ever call `POST /v1/observations` with `kind: "drift"`.
- **`ingestion` / `cv-service` wiring:** new `drift_client.py` in each (same fire-and-forget, fail-open pattern as `incident_client.py` — drift-monitor being unreachable never blocks or slows either service). `ingestion/pipeline.py` reports every accepted `sensor_ping`'s numeric features; `cv-service/pipeline.py` reports every finding's geometry vector (published or review-routed, before that decision is made).
- **`docker-compose.yml`:** new `drift-monitor` service block (port 9109, same healthcheck pattern); `ingestion` and `cv-service` gain `PRISM_DRIFT_MONITOR_URL` + `depends_on: drift-monitor`.
- **`.github/workflows/ci.yml`:** `pip install -e drift-monitor` + `scipy>=1.11` added to the Unit tests job (not the Golden-path e2e job — that job never imports the package directly, it only needs `drift-monitor/Dockerfile` to build via `make demo`'s compose chain, which it now does as an ingestion/cv-service dependency).
- **`.github/workflows/release-packages.yml`:** `drift-monitor` added to the GHCR publish matrix **now**, proactively — Phase 15 had to fix a real gap where `scenario-engine`/`incident-engine` were missing from this exact matrix after v1.1.0 shipped; not repeating that miss this time.
- **`Makefile`:** `setup` installs `drift-monitor` editable; new `phase16-check` target. **`requirements-dev.txt`:** `scipy>=1.11` added.
- **`tests/unit/test_drift_monitor.py`** (9 tests) — the baseline gate (never built from synthetic data, freezes at exactly the configured count), stable traffic never flags drift, shifted traffic flags exactly the shifted features, both feature groups, and the three pure statistical functions in isolation.
- **`tests/unit/test_drift_integration.py`** (1 test) — real scenario-engine + real ingestion + real drift-monitor + real incident-engine, all actual HTTP servers, no mocks: a real baseline earned from the live simulator, then scenario-engine's own foreshadowed `drift_signature` outcome (100%-weighted for determinism) actually trips the breaker via `drifted_features`.

## Bug caught during build, not reported after the fact

An early smoke test of the scalar (`telemetry_numeric`) tracker showed `odometer_km` registering as "drifted" on the **very first** comparison window — before any real shift had been introduced anywhere. Root cause: `odometer_km` is a monotonically increasing cumulative counter in both `FleetSimulator` (ingestion's live source) and scenario-engine's `sampler.py` (`state.odometer_km + tick * 0.01`, only ever added to). A KS test comparing two different time windows of a monotonic counter will find them statistically distinguishable on every single run, regardless of any actual anomaly — it's measuring elapsed ticks, not behavior. Fixed by excluding `odometer_km` from `TELEMETRY_NUMERIC_FIELDS` (`features.py`), with the reasoning recorded in a code comment so it isn't silently reintroduced later.

## A confound worth being explicit about in the live proof below

The live proof (and integration test) intentionally builds the real baseline from `ingestion`'s live-mode `FleetSimulator` (seed 42) and then compares it against a window from `scenario-engine`'s independently-seeded chaos source (seed 7) — this is the correct design (ADR-005: never let synthetic data build the baseline it's later judged against). One side effect: `heading_deg` and `fuel_level_pct`, which scenario-engine's `drift_signature` code path does **not** intentionally shift, sometimes *also* show up as `drifted: true` in the raw output below. That's because both simulators pick an arbitrary fixed value for those two fields per asset at startup and never change them again — two independently-seeded simulators simply landed on different constants, and a KS test correctly reports two different constants as different distributions. This is a real, disclosed limitation of comparing two separately-seeded synthetic simulators for *this specific proof's methodology*, not a flaw in the statistics or in the production wiring (a real deployment only ever has one live fleet feeding both the baseline and the comparison window). The three features scenario-engine's `drift_signature` branch actually shifts — `speed_mph`, `latitude`, `longitude` — are the reliable signal: they show the strongest, most consistent separation (p-values orders of magnitude below the 0.05 threshold, KS statistic climbing to 1.0 as the window fills with shifted samples) and are what should be read as "the real proof."

## Live proof — real scenario-engine + real ingestion + real drift-monitor + real incident-engine, not mocks

Four real HTTP servers (`uvicorn`, no mocks), driven together in one session, mirroring `tests/unit/test_drift_integration.py` exactly.

**1. `/health` before any observations — honestly non-ready:**

```json
{"baseline_ready": false, "assets": {}}
```

**2. Baseline earned from 27 ticks of the live simulator (20 real `sensor_ping`s reported, `PRISM_DRIFT_BASELINE_SAMPLES=15`):**

```json
{
  "baseline_ready": true,
  "assets": {
    "PRISM-AST-001": {
      "groups": {
        "telemetry_numeric": {"baseline_ready": true, "baseline": {"mode": "real", "sample_count": 15}}
      }
    }
  }
}
```

**3. Breaker stays closed on clean live traffic:**

```json
{"asset_id": "PRISM-AST-001", "state": "closed", "trip_reason": null, "drifted_feature_count": 0}
```

**4. scenario-engine weighted 100% to `drift_signature`, 12 ticks through real ingestion → drift-monitor → incident-engine. `GET /breakers/PRISM-AST-001`:**

```json
{
  "asset_id": "PRISM-AST-001",
  "state": "open",
  "incident_id": "inc_11754a0889b3",
  "trip_reason": "drifted_features",
  "drifted_feature_count": 5,
  "opened_at": "2026-08-03T17:27:20.946945Z"
}
```

**5. The incident-engine audit journal (`GET /v1/journal`), first `drift` observation that crossed the threshold (drifted_feature_count=2, before the window fully saturated):**

```json
{
  "event": "observation",
  "asset_id": "PRISM-AST-001",
  "detail": {
    "kind": "drift",
    "group": "telemetry_numeric",
    "drifted_feature_count": 2,
    "tests": [
      {"feature": "speed_mph", "drifted": false, "pvalue": 0.0544},
      {"feature": "latitude", "drifted": true, "pvalue": 3.67e-05},
      {"feature": "longitude", "drifted": true, "pvalue": 0.0144},
      {"feature": "heading_deg", "drifted": false, "pvalue": 0.330},
      {"feature": "fuel_level_pct", "drifted": false, "pvalue": 0.330}
    ]
  }
}
```

followed by `"event": "incident_opened"` and `"event": "breaker_transition", "detail": {"from": "closed", "to": "open", "reason": "drifted_features"}` — the exact same trip → incident → breaker_transition sequence Phase 14 documented, just with `drift` as the trigger instead of `quarantine_rate`, proving the dormant wiring Phase 14 shipped works exactly as designed once a real producer exists.

## How to verify yourself

```bash
# Unit + integration tests (9 + 1), no Docker required:
pip install -e drift-monitor
PYTHONPATH=<repo>/observability/otel pytest -q tests/unit/test_drift_monitor.py tests/unit/test_drift_integration.py
# → 10 passed

# Full suite (confirms nothing else regressed):
pytest -q tests/unit
# → 125 passed, 2 skipped

make phase16-check   # lint + full unit suite

# Live compose (after `make demo` or `docker compose up -d --build drift-monitor incident-engine`):
curl -sS http://127.0.0.1:9109/health
curl -sS http://127.0.0.1:9109/v1/status
```

## Deferred (unchanged from the release plan)

| Item | To |
|------|-----|
| Dagster orchestration (drift-monitor as a graph node, drift → synthetic reseed edge) | Phase 17 |
| OPA/Rego promotion of `drifted_features` (and every other trip policy) | Phase 18 |
| Golden-path e2e extended to a full chaos scenario including a drift trip | Phase 19 |

## CI

Pending — will link the concluded green run in a follow-up commit once pushed (same pattern as every prior phase).

## Stop

Phase 16 complete. **Do not start Phase 17** without explicit go-ahead.
