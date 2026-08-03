# Release plan

How PRISM phases map to semver. A tagged release closes a coherent capability
cut, not an arbitrary commit.

## Tracks

| Track | Scope | Status |
|-------|--------|--------|
| **v1.0.0** | Phases 0–11 — data spine through golden-path demo | Tagged |
| **v1.1.0** | Phases 12–15 — chaos/audit core (scenario-engine, two-layer validation, incident-engine, Breaker Board) | Tagged |
| **v1.2.0** | Phases 16–19 — drift-monitor, Dagster, OPA/Rego, case study | In progress |
| **v1.x.y** | Patch / docs / CI only | As needed |

Phase completion records: [`docs/phases/`](./phases/) (`PHASE_00` …).

## v1.0.0 (shipped)

Full Phases 0–11 portfolio close-out. See git tag `v1.0.0` and
[PACKAGING_PLAN.md](./PACKAGING_PLAN.md).

## v1.1.0 gate (Phases 12–15)

| Phase | Capability |
|------:|------------|
| 12 | Scenario-engine (seeded, audited chaos) + ADR-005 |
| 13 | Two-layer validation (Pydantic triage → Pandera gate) |
| 14 | Per-asset circuit breaker + incident-engine |
| 15 | Cockpit Breaker Board + copilot breaker/incident tools |

**Checklist:**

- [x] Phase 12 complete under `docs/phases/PHASE_12_COMPLETION.md`
- [x] Phase 13 complete under `docs/phases/PHASE_13_COMPLETION.md`
- [x] Phase 14 complete under `docs/phases/PHASE_14_COMPLETION.md`
- [x] Phase 15 complete under `docs/phases/PHASE_15_COMPLETION.md`
- [x] Git tag `v1.1.0` + GitHub Release + GHCR republish

## v1.2.0 gate (Phases 16–19)

| Phase | Capability |
|------:|------------|
| 16 | drift-monitor: honest-baseline-gated KS test + centroid distance + KS-on-norms; feeds incident-engine's dormant `drifted_features` policy |
| 17 | Dagster orchestration (lakehouse + drift-monitor + optional drift→reseed edge) |
| 18 | OPA/Rego promotion of trip policies |
| 19 | Golden-path e2e chaos scenario + v1.2.0 release + case study |

**Checklist:**

- [x] Phase 16 complete under `docs/phases/PHASE_16_COMPLETION.md`
- [x] Phase 17 complete under `docs/phases/PHASE_17_COMPLETION.md`
- [x] Phase 18 complete under `docs/phases/PHASE_18_COMPLETION.md`
- [ ] Phase 19 complete
- [ ] Git tag `v1.2.0` + GitHub Release + GHCR republish

## Tagging

```text
vMAJOR.MINOR.PATCH
```

- Tag only from `main` after the track’s phase completion docs exist.
- Changelog section required before tagging (see root `CHANGELOG.md`).
- Container publishes happen **at tag time** (see PACKAGING_PLAN).
