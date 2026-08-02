# ADR 005 — Earned-evidence policy (no unearned capability claims)

**Status:** Accepted  
**Date:** 2026-08  
**Phases:** 12+ (`scenario-engine/`, later `incident-engine/`, `drift-monitor/`)

## Context

v1.1 / v1.2 add chaos injection, per-asset circuit breakers, and drift
detection. Each of those surfaces can *look* ready in a demo while quietly
lying: a drift detector that scores against a made-up Gaussian baseline, an
incident engine that “routes to Slack” with no proven channel, or a scenario
source that presents synthetic events as live fleet telemetry.

ADR-004 already forbids fabrication in Ask PRISM answers. This ADR extends the
same honesty bar to **infrastructure and subsystem readiness claims**, matching
Vulcan’s catalog-honesty discipline and Argus’s `baseline_ready` gate.

## Decision

1. **No unearned capability claims.** A subsystem may not report ready / healthy
   for a capability it has not earned evidence for.
2. **Synthetic is labeled.** Scenario-engine events always carry
   `synthetic_scenario: true` and a `scenario_id`. They must never be presented
   as live fleet telemetry (same spirit as Argus ADR-007 separate-sink rule).
3. **Drift waits for a real baseline.** When `drift-monitor` lands (Phase 16),
   statistical tests run only after `baseline_ready` is true from enough real
   validated samples. A synthetic Gaussian is cold-start fallback only and is
   discarded once real data exists. `/health` stays non-ready until then.
4. **Incidents do not fake routing.** The incident engine may not auto-route to
   a notification channel it has not proven works. Local mock webhook + inbox
   is fine (ADR-001); claiming Slack/PagerDuty delivery without evidence is not.
5. **Completion reports obey the same rule.** Phase completion docs and README
   claims must match runnable proof — not aspirational wiring.

## Alternatives considered

| Option | Why not |
|--------|---------|
| Demo-ready defaults that fake baselines | Greenwashes drift; breaks portfolio honesty |
| Silent synthetic co-ownership of bronze tables | Contaminates gold; violates contract-first continuity |
| “Ready” health while features are stubs | Same failure mode ADR-004 already blocked for copilot |

## Consequences

- Phase 12 ships `scenario-engine/` with audit journals and synthetic tags before
  any claim of “auditable chaos.”
- Later phases (drift, breakers, orchestration) must gate readiness explicitly.
- Foundation / ADR index tests treat ADR-005 as a required artifact.

## Compliance

- ADR-001 cost-safety still applies (no paid channels required for green CI).
- ADR-004 non-fabrication remains the bar for Ask PRISM text answers.
