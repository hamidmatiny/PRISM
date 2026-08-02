# Release plan

How PRISM phases map to semver. A tagged release closes a coherent capability
cut, not an arbitrary commit.

## Decision (v1.0.0)

**`v1.0.0` covers the full Phases 0–11 portfolio build.**

The mid-build plan (written after Phase 5) sketched a Vulcan-style split
(`v1.0.0` = 0–5, `v1.1.0` = 6–7, `v1.2.0` = 8–9, `v1.3.0` = 10–11). That split
made sense while phases were still in flight. By the time of the first tag,
Phases 0–11 were already complete on `main`, so inventing intermediate tags
after the fact would misrepresent history.

| Track | Scope | Status |
|-------|--------|--------|
| **v1.0.0** | Phases 0–11 — data spine, control plane, AWS/Azure IaC (validate-only), cockpit, Ask PRISM, observability/security, golden-path demo | **This release** |
| **v1.0.x** | Correctness / docs / CI / packaging fixups only | Future patches |
| **v1.1.0+** | Net-new capability after the portfolio close-out | Future minors |

Phase completion records live under [`docs/phases/`](./phases/)
(`PHASE_00_COMPLETION.md` … `PHASE_11_COMPLETION.md`).

## v1.0.0 gate

| Phase | Capability |
|------:|------------|
| 0 | Monorepo, ADR-001, CI validate-only |
| 1 | Telemetry/CV contracts + ingest → bronze |
| 2 | Lakehouse bronze→silver→gold + dbt |
| 3 | CV service + confidence-gated review queue |
| 4 | Activation gateway (Redshift + Snowflake contract) |
| 5 | Control plane (RBAC review → gold writeback) |
| 6 | AWS platform Terraform (validate / plan / checkov in CI) |
| 7 | Azure DR warm-standby Terraform + failover runbook |
| 8 | Digital-twin cockpit (Vue 3 + Three.js) |
| 9 | Tool-grounded AI copilot (Ask PRISM) |
| 10 | OpenTelemetry, LES dashboards, secrets rotation, security audits |
| 11 | Golden-path e2e, `make demo`, finalized docs / screenshots |

**Checklist:**

- [x] Phases 0–11 complete under `docs/phases/PHASE_NN_COMPLETION.md`
- [x] `docker compose` / `make demo` path healthy with zero cloud credentials (ADR-001)
- [x] Golden-path e2e + prior CI gates green on `main`
- [x] Apache-2.0 `LICENSE` at repo root
- [x] Git tag `v1.0.0` + GitHub Release
- [x] GHCR publish of core service images per [PACKAGING_PLAN.md](./PACKAGING_PLAN.md)

## Tagging

```text
vMAJOR.MINOR.PATCH
```

- Tag only from `main` after the track’s phase completion docs exist.
- Changelog section required before tagging (see root `CHANGELOG.md`).
- Container publishes happen **at tag time**, not continuously on every phase
  commit (see PACKAGING_PLAN).
