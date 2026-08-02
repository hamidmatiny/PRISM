# Release plan

How PRISM phases map to semver tracks. Same discipline as Vulcan: a tagged
release closes a coherent capability cut, not an arbitrary commit.

## v1.0.0 — Data spine + control plane (Phases 0–5)

**Cut justification:** Phases 0–5 close the end-to-end local loop that makes
PRISM a product, not a pile of stubs:

| Phase | Capability |
|------:|------------|
| 0 | Monorepo, ADR-001, CI validate-only |
| 1 | Telemetry/CV contracts + fleet → bronze |
| 2 | Lakehouse bronze→silver→gold + dbt |
| 3 | CV service + confidence-gated review queue |
| 4 | Activation gateway (Redshift + Snowflake contract) |
| 5 | Control plane (RBAC review of real pending findings → gold writeback) |

That is the **full data spine plus the human-in-the-loop control plane**. A
reviewer can ingest fleet telemetry, land gold, run CV, activate warehouses,
and approve low-confidence findings — all via `docker compose` with zero cloud
credentials (ADR-001).

Phases 6–11 add cloud packaging, DR, cockpit UX, copilot, and demo polish.
Those improve operability and surface area but are not required to prove the
architecture thesis (“one gold table, many warehouses” + no auto-actioned
low-confidence CV).

**v1.0.0 gate (checklist):**

- [x] Phases 0–5 complete with `PHASE_N_COMPLETION.md`
- [x] `docker compose up` path healthy for ingestion, cv-service, activation-gateway, control-plane
- [x] Conformance / review continuity against live `.data` where claimed
- [ ] Git tag `v1.0.0` + GHCR publish per [PACKAGING_PLAN.md](./PACKAGING_PLAN.md) (deliberate, not mid-phase)

## Phase → release track

| Track | Phases | Theme |
|-------|--------|--------|
| **v1.0.0** | 0–5 | Contracts, ingest, lakehouse/dbt, CV, activation, control plane |
| **v1.1.0** | 6–7 | AWS platform Terraform modules + Azure DR warm-standby (validate in CI; apply out-of-band) |
| **v1.2.0** | 8–9 | Digital-twin cockpit (Vue 3 + Three.js) + tool-grounded AI copilot |
| **v1.3.0** | 10–11 | Observability/security hardening + productionization / demo script close-out |

Minor bumps may absorb fixups (`fix(...)`) without waiting for the next track.
Patch releases (`v1.0.x`) are for correctness / docs / CI only.

## Tagging

```text
vMAJOR.MINOR.PATCH
```

- Tag only from `main` after the track’s phase completion docs exist.
- Changelog section required before tagging (see root `CHANGELOG.md`).
- Container publishes happen **at tag time**, not continuously on every phase
  commit (see PACKAGING_PLAN).
