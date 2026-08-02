# incident-engine

Per-asset circuit breaker (Phase 14) — the direct answer to "pause the
source, not the whole pipeline." FSM shape and vocabulary adapted from
Argus's incident-engine concept, reimplemented in Python against PRISM's
own event kinds and trip policies — see
[`docs/phases/PHASE_14_COMPLETION.md`](../docs/phases/PHASE_14_COMPLETION.md)
for exactly what was reused vs. adapted.

## FSM

```
closed --[trip policy fires]--> open --[cooldown elapses]--> half_open
   ^                                                             |
   |----------------[probe observation passes]------------------|
   |                                                              |
   +-----[probe observation fails: same incident, retrip]--------+
```

Scoped **per `asset_id`** — tripping one asset never touches any other
asset's state, and every other asset keeps flowing through the same shared
`ingestion` / `cv-service` / `activation-gateway` containers unaffected.

## Trip policies (`policies/default_policies.yaml`)

- `quarantine_rate`: rolling window of the last 5 per-asset ingestion
  outcomes; trips when quarantined/window > 15%.
- `consecutive_qa_failures`: 3 consecutive cv-service low-confidence
  (review-routed) findings for one asset, reset on any published finding.
- `drifted_features`: ≥2 drifted features — no producer exists until Phase
  16's drift-monitor ships `drift` observations. Real, correctly
  implemented, dormant — never fabricated readiness (ADR-005).

Declarative YAML for now; Phase 18 promotes these to real OPA/Rego.

## API

- `POST /v1/observations` — `{asset_id, kind, detail}`, kind one of
  `ingestion_accepted | ingestion_quarantined | qa_pass | qa_fail | drift`.
- `GET /breakers` / `GET /breakers/{asset_id}`
- `GET /incidents?status=open|acknowledged|resolved`
- `GET /incidents/{id}`
- `POST /incidents/{id}/acknowledge`
- `POST /incidents/{id}/resolve` — manual override, force-closes the breaker.
- `POST /v1/webhook-test/receive` / `GET /v1/webhook-test/inbox` — mock
  alerting (ADR-001: no real Slack/PagerDuty).
- `GET /v1/journal` — tail the permanent audit journal.

## Who calls this

- `ingestion` reports `ingestion_accepted` / `ingestion_quarantined` per
  event after its two-layer validation gate (Phase 13) decides.
- `cv-service` reports `qa_pass` / `qa_fail` per finding (published vs.
  review-routed) and, before deciding publish-vs-review, checks
  `GET /breakers/{asset_id}` — if open, the finding is forced into human
  review regardless of confidence.

Both integrations are best-effort: incident-engine being unreachable never
breaks ingestion or cv-service, it just means breaker state doesn't update
for that observation (same graceful-degradation pattern the rest of PRISM
uses for scenario-engine/otel-collector).
