# Case study — one seeded chaos run, start to finish

**Precedent:** this follows Vulcan's and Argus's case-study format — walk through one specific, reproducible run rather than describe the system in the abstract. Every number below is real: reproduced by re-running `scenario-engine`'s sampler with `seed=14` against the exact asset list PRISM's demo stack uses (`PRISM-AST-001`, `PRISM-AST-002`, `PRISM-AST-003`), not paraphrased from a log.

## The question this answers

PRISM's whole v1.1/v1.2 arc exists to answer one operational question: *when one asset in a fleet starts producing bad data, does the system stay up for everyone else, notice the one bad asset, and let a human close the loop — without anyone hand-editing a database or restarting a container?*

This case study runs that exact scenario, seeded and reproducible, and shows every hop.

## The setup

- **Seed:** `14`
- **Assets:** `PRISM-AST-001`, `PRISM-AST-002`, `PRISM-AST-003` — the same three the demo stack seeds by default
- **Weights:** `scenario-engine`'s default distribution (`clean: 45%`, `sensor_corrupt: 10%`, `contract_violation: 10%`, `cv_low_confidence: 10%`, `cv_high_confidence: 10%`, `drift_signature: 10%`, `stalled_source: 5%`) — nothing hand-tuned to force the outcome
- **Trip policy in force:** `incident-engine/policies/rego/quarantine_rate.rego` — `window_min = 5`, `threshold = 0.15` (open the breaker once 5 consecutive ingestion outcomes for one asset show a rejected rate above 15%)

`scenario-engine` samples one outcome per tick, cycling through the three assets round-robin, so `PRISM-AST-001` gets ticks 1, 4, 7, 10, 13, 16, 19, ... Because the sampler is seeded, this exact sequence — for this exact asset list — reproduces byte-for-byte every time; that's the whole point of the Phase 12 discipline this case study is exercising.

## Timeline

| Tick | Asset | Sampled outcome | PRISM-AST-001's rolling 5-window | Rate |
|-----:|-------|------------------|-----------------------------------|-----:|
| 1 | PRISM-AST-001 | `contract_violation` | `[Q]` | — (window not full) |
| 4 | PRISM-AST-001 | `clean` | `[Q, ok]` | — |
| 7 | PRISM-AST-001 | `clean` | `[Q, ok, ok]` | — |
| 10 | PRISM-AST-001 | `contract_violation` | `[Q, ok, ok, Q]` | — |
| **13** | **PRISM-AST-001** | **`sensor_corrupt`** | **`[Q, ok, ok, Q, Q]`** | **60% — over the 15% threshold** |
| 16 | PRISM-AST-001 | `sensor_corrupt` | `[ok, ok, Q, Q, Q]` | 60% — still open |
| 19 | PRISM-AST-001 | `cv_low_confidence` | `[ok, Q, Q, Q, ok]` | 60% — still open |

(`Q` = an outcome that fails ingestion's validation and gets reported to incident-engine as `ingestion_quarantined` — both `sensor_corrupt`, which fails the fast Pydantic pre-triage, and `contract_violation`, which fails the stricter Pandera gate, count. `cv_low_confidence` and `clean` do not.)

By tick 13 — the fifth time `PRISM-AST-001` has been sampled at all — 3 of its last 5 outcomes were quarantine-worthy: 60%, well past the 15% line. `incident-engine`'s OPA/Rego policy (`quarantine_rate.rego`, promoted from a Python threshold in Phase 18) evaluates this on every observation it receives; the moment the rolling window crosses the line, it trips.

## What happens when it trips

1. **`incident-engine` opens `PRISM-AST-001`'s breaker, and only that one.** `PRISM-AST-002` and `PRISM-AST-003` are on their own independent trackers — this run's chaos didn't touch either of them, and their breakers stay `closed` throughout. This is the per-asset scoping Phase 14 built: one bad asset never takes down the shared `ingestion` / `cv-service` / `activation-gateway` containers, and it never touches another asset's state.
2. **An incident opens**, `trip_reason: "quarantine_rate"`, with a fresh `incident_id`. Every transition — the trip itself, and everything that follows — writes to `incident-engine`'s append-only audit journal.
3. **The Breaker Board (Phase 15) and Ask PRISM (Phase 15's `query_breakers`/`query_incidents` tools) both read this from the same source of truth** — `incident-engine`'s `/breakers` and `/incidents` endpoints — so there's no second code path to drift out of sync with what actually happened.

## The human closes the loop

This is the part that's easy to build as a demo and easy to get wrong for real: does resolving an incident actually put the system back the way it was, or does it just change a status label?

- `POST /incidents/{id}/acknowledge` — status moves to `acknowledged`, timestamped, journaled. The breaker is still `open` — acknowledging doesn't silently un-trip anything.
- `POST /incidents/{id}/resolve` — status moves to `resolved`, and **the breaker itself closes in the same call**: state back to `closed`, `incident_id` cleared, `trip_reason` cleared, the rolling quarantine window reset. `PRISM-AST-001` goes back to normal, immediately, over the real API — not on a timer, not eventually.
- The cockpit's Breaker Board reads this the instant it next polls, through the exact same `/proxy/incident/breakers/PRISM-AST-001` path this case study's automated proof hits directly — there's no separate cockpit-side state to reconcile.

## Ask PRISM, grounded in what actually happened

Asking *"What happened to asset PRISM-AST-001? Is its circuit breaker open right now?"* after the run above routes through `query_breakers` and `query_incidents` (ADR-004: every answer must be grounded in a real tool call against real data, never fabricated), and the answer is built only from what `incident-engine` actually recorded for this asset — the trip, the reason, and the resolution.

## What this proves, and what it doesn't

**Proves:** the seeded-chaos → per-asset breaker → human-resolvable → grounded-copilot chain is real, reproducible, and wired end to end — not four features that happen to sit in the same repo.

**Doesn't try to prove:** that a 15% quarantine-rate threshold or a `window_min` of 5 is the "correct" number for a real fleet. Those are Rego policy values, chosen to be legible for a portfolio demo (`docs/adr/006-dagster-orchestration.md`'s sibling, the Phase 18 Rego promotion, made changing them a policy-file diff, not an application code change, precisely because the real numbers should be tuned against real fleet data, not guessed once and left alone).

## Reproduce this yourself

```python
from pathlib import Path
from fastapi.testclient import TestClient
from prism_scenario_engine.api import create_app
from prism_scenario_engine.config import ScenarioConfig

cfg = ScenarioConfig(
    data_root=Path("/tmp/scn-repro"),
    seed=14,
    scenario_id="scn_phase19_chaos",
    asset_ids=("PRISM-AST-001", "PRISM-AST-002", "PRISM-AST-003"),
)
client = TestClient(create_app(cfg))
for _ in range(20):
    ev = client.get("/v1/next-event").json()
    print(ev["tick"], ev["asset_id"], ev.get("outcome"))
# Same seed -> byte-identical sequence, every time (Phase 12 discipline).
```

Or, against the full live stack (`make demo`, then see `docs/phases/PHASE_19_COMPLETION.md`'s "How to verify yourself" section): drive it through the real HTTP path exactly as `tests/e2e/test_golden_path.py::test_chaos_golden_path` does, end to end, no shortcuts.
