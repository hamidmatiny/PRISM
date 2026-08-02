# Phase 13 — Two-layer Pydantic → Pandera validation hardening

## What changed

`ingestion/`'s single-layer Pydantic gate becomes two independent, differently-technologied gates, adapted from hydra-data-factory's structural-pre-check-then-contract-gate pattern (PRISM's own field set and taxonomy, not hydra's AV-specific one):

- **Layer 1 — structural (`validate.py` + new `corruption.py`).** Unchanged Pydantic models (`SensorPing`, `CameraFrameMetadata`) still do the wire-format check. New: every rejection is now classified into a stable `corruption_type` enum (`missing_required_field`, `invalid_timestamp`, `invalid_numeric_value`, `malformed_identifier`, `malformed_storage_uri`, `malformed_geo`, `scenario_field_inconsistent`, `schema_validation`). The live `FleetSimulator` already tagged its injected corruptions with a `_corruption` strategy hint that was being silently discarded before this phase (`validate.py` stripped any `_`-prefixed key before validation and never looked at it again) — the classifier now reads that hint as ground truth when present, and falls back to inspecting `pydantic.ValidationError.errors()` locations/types when it isn't (scenario-engine's payloads carry no hint).
- **Layer 2 — contract (new `contract_gate.py`).** A Pandera `DataFrameSchema` per event kind, run on the Pydantic-cleaned record wrapped in a 1-row DataFrame. This is a genuinely independent re-assertion against the bronze/analytics storage contract, not a restatement of Layer 1 — see "the concrete gap" below for what it catches that Layer 1 structurally cannot.
- **DLQ envelope (`bronze.py`):** `write_dlq_record` now writes `rejection_reason` (human-readable, was `reason`), `corruption_type`, and `gate` (`"structural"` | `"contract"`) — so a DLQ reader never has to guess which layer rejected a record or why.
- **Stats (`pipeline.py`):** `IngestPipeline.stats.by_corruption_type` is a live rolling counter, exposed through `/health`.
- **`ingestion/pyproject.toml`:** added `pandera[pandas]>=0.20` as a real dependency (flows into CI automatically via the existing `pip install -e ingestion` step in both the `test` and `e2e` jobs — no CI YAML edit needed).

## The concrete gap this closes

A sensor ping with `latitude == longitude == 0.0` ("null island") is **inside** Pydantic's declared `-90..90` / `-180..180` ranges, so it passed Layer 1 cleanly before this phase — even though `(0, 0)` is never a real PRISM fleet position. Verified interactively before writing any code:

```python
>>> validate_event("sensor_ping", {..., "latitude": 0.0, "longitude": 0.0, "speed_mph": 25.0, "odometer_km": 4200.0})
ok=True   # <- before Phase 13: silently accepted to bronze
```

After Phase 13, the same record is rejected at Layer 2 with `corruption_type=malformed_geo`, `gate=contract`. This is now a permanent regression test: `test_contract_gate_catches_null_island_that_structural_gate_misses` in `tests/unit/test_ingestion.py`.

Why scenario-engine's own `contract_violation` payloads don't exercise this in the wild: its current sensor_ping payload sets `speed_mph=999.0` and `odometer_km=-5.0` *together with* `latitude=longitude=0.0`, so Layer 1 already rejects it on the numeric fields before Layer 2 ever runs. The live proof below (300 real ticks) shows real Layer-1 rejections at scale; the dedicated unit test isolates the Layer-2 case scenario-engine's fixed payloads happen to mask.

## Live proof — real scenario-engine + real ingestion, not mocks

`scenario-engine` was started as an actual local process (`uvicorn`, seed 42) and `ingestion`'s real pipeline pulled 300 ticks from it over real HTTP, through the real two-layer gate:

```
stats: {
  "emitted": 69, "accepted": 51, "rejected": 18, "skipped": 231,
  "by_corruption_type": {
    "missing_required_field": 10,
    "malformed_storage_uri": 3,
    "invalid_numeric_value": 5
  }
}
```

Sample DLQ record from that run (`.data/bronze/_dlq/...json`):

```json
{
  "corruption_type": "invalid_numeric_value",
  "gate": "structural",
  "kind": "sensor_ping",
  "rejection_reason": "2 validation errors for SensorPing\nspeed_mph\n  Input should be less than or equal to 120 ...\nodometer_km\n  Input should be greater than or equal to 0 ...",
  "record": { "asset_id": "PRISM-AST-002", "latitude": 0.0, "longitude": 0.0, "odometer_km": -5.0, "scenario_outcome": "contract_violation", "speed_mph": 999.0, ... }
}
```

`accepted (51) + rejected (18) == emitted (69)`; no accepted record carries a `corruption_type`.

## Fixes shipped alongside (requested before Phase 13 started)

1. **Local (non-Docker) test setup was undocumented.** Added `requirements-dev.txt` (mirrors `.github/workflows/ci.yml`'s `test`-job install list exactly), a `make setup` target that installs it plus every service's editable install, and a new README section ("Local (non-Docker) test setup") explaining Python 3.12 and Java 17 prerequisites.
2. **`test_medallion_local_spark` hard-failed with no local JVM.** It now checks `shutil.which("java")` and wraps the session build in a try/except, `pytest.skip`-ing with a clear reason instead of failing red when Java isn't available locally (CI always has it via `actions/setup-java`).
3. **"Verify it yourself" standard.** `docs/phases/README.md` now states the requirement explicitly; this document follows it below.
4. **Completion-timing rule** (process, not code): don't report a phase done until CI shows a concluded, green run — applies going forward.

## Why this is Cursor's Phase 13, done differently

Cursor hit its monthly usage limit before starting this phase. With the user's explicit authorization, this phase was designed and implemented directly against the real repository (cloned fresh, changes committed and pushed with a user-provided scoped PAT) instead of through Cursor. All verification below was run in an isolated Linux sandbox with **no Docker and no outbound access to GitHub release assets / astral.sh** — so unlike every prior phase, there is no live `make demo` / `make e2e` run to report here. Python 3.12 wasn't obtainable in that sandbox either (no root, no reachable package mirror for it); the unit-test verification below ran on Python 3.10 with a small, disclosed stdlib compatibility shim (`datetime.UTC`, `typing.Self`, `enum.StrEnum` — all real Python 3.11+ additions this codebase uses, backported for local verification only, never part of the shipped code). This is disclosed, not hidden, in keeping with ADR-005. **The Docker demo + `make e2e` run in "Verify it yourself" below is the step you should run yourself as the authoritative confirmation** — everything else here was independently verified but on a substitute interpreter.

## CI

First push (`d4a347a`) failed: a Phase-11-era regression test in
`test_foundation.py` hardcodes the expected `docs/phases/PHASE_*_COMPLETION.md`
set and required-file list; it correctly caught that `PHASE_13_COMPLETION.md`
wasn't accounted for. Fixed in `64544b0` (bumped the range and required-files
list) after reproducing the exact failure locally first, in a disposable
diagnostic copy with real editable installs (not the pythonpath-override
shortcut used elsewhere in this doc) to rule out the shortcut itself as the
cause before touching anything.

Final concluded, green run on `64544b0`: [CI run
30757428347](https://github.com/hamidmatiny/PRISM/actions/runs/30757428347) —
Lint, Unit tests, Cockpit build, both Terraform matrix legs, AWS terraform
plan artifact, and the live Golden-path e2e all passed, 4m 44s total. This
run wasn't reported until it showed a concluded `Status Success`, not while
any job was still in progress.

## Verify it yourself

```bash
git pull
python3.12 -m venv .venv && source .venv/bin/activate   # real 3.12, not a substitute
make setup
make lint
# expect: "All checks passed!" / "N files already formatted"

make test
# expect: 94 passed (was 88 before this phase), 1-2 skipped depending on local Java.
# Look for the 6 new tests: pytest -q tests/unit/test_ingestion.py -v | grep -i corrupt

# Live proof, on your machine, against the real Docker stack:
make demo
curl -s http://127.0.0.1:9105/health | python3 -m json.tool
# expect a "by_corruption_type" key inside "stats" that did not exist before this phase

make e2e
make down
```

To see the null-island fix directly:

```bash
source .venv/bin/activate
python3 -c "
from prism_ingestion.validate import validate_event
r = validate_event('sensor_ping', {
    'schema_version': '1.0.0', 'event_type': 'sensor_ping',
    'asset_id': 'PRISM-AST-001', 'device_id': 'PRISM-DEV-001',
    'timestamp': '2026-08-01T12:00:01Z', 'speed_mph': 25.0,
    'latitude': 0.0, 'longitude': 0.0, 'heading_deg': 0.0, 'odometer_km': 4200.0,
})
print(r.ok, r.gate, r.corruption_type)
"
# expect: False contract malformed_geo
```

## Paths to open if you distrust this summary

- `ingestion/src/prism_ingestion/corruption.py` — the full classification logic, both layers.
- `ingestion/src/prism_ingestion/contract_gate.py` — the Pandera schemas and the null-island check.
- `ingestion/src/prism_ingestion/validate.py` — how the two layers are wired together.
- `tests/unit/test_ingestion.py` — search for `Phase 13` to find the 6 new tests.
- `tests/unit/test_lakehouse.py::test_medallion_local_spark` — the graceful-skip fix.
- `requirements-dev.txt`, `Makefile` (`setup` target), `README.md` ("Local (non-Docker) test setup").
