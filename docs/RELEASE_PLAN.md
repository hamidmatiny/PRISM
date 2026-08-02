# Release plan

How PRISM phases map to semver. A tagged release closes a coherent capability
cut, not an arbitrary commit.

## Tracks

| Track | Scope | Status |
|-------|--------|--------|
| **v1.0.0** | Phases 0–11 — data spine through golden-path demo | Tagged |
| **v1.1.0** | Phases 12–15 — chaos/audit core (scenario-engine, two-layer validation, incident-engine, Breaker Board) | **In progress** (Phase 12+) |
| **v1.2.0** | Phases 16–19 — drift-monitor, Dagster, OPA/Rego, case study | Planned |
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

**Checklist (open):**

- [x] Phase 12 complete under `docs/phases/PHASE_12_COMPLETION.md`
- [ ] Phases 13–15 complete
- [ ] Git tag `v1.1.0` + GitHub Release + GHCR republish

## Tagging

```text
vMAJOR.MINOR.PATCH
```

- Tag only from `main` after the track’s phase completion docs exist.
- Changelog section required before tagging (see root `CHANGELOG.md`).
- Container publishes happen **at tag time** (see PACKAGING_PLAN).
