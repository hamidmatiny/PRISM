# incident-engine

Per-asset circuit breaker (Phase 14) with OPA/Rego trip policies (Phase 18).
FSM shape adapted from Argus's incident-engine concept; trip thresholds are
**policy-as-code** under [`policies/rego/`](policies/rego/) — change a `.rego`
file (and its `*_test.rego`), not `fsm.py`.

See [`docs/phases/PHASE_18_COMPLETION.md`](../docs/phases/PHASE_18_COMPLETION.md).

| | |
|---|---|
| **Port (host)** | **9108** |
| **OPA (host)** | **9113** (`opa run --server`, Compose) |

## FSM

```
closed --[Rego trip fires]--> open --[cooldown elapses]--> half_open
   ^                                                             |
   |----------------[probe observation passes]------------------|
   |                                                              |
   +-----[probe observation fails: same incident, retrip]--------+
```

Scoped **per `asset_id`**.

## Trip policies (`policies/rego/*.rego`)

| Rego package | Reason string | Rule |
|---|---|---|
| `prism.quarantine_rate` | `quarantine_rate` | window ≥ 5 and quarantined/window > 0.15 |
| `prism.consecutive_failures` | `consecutive_qa_failures` | streak ≥ 3 |
| `prism.drift_count` | `drifted_features` | drifted feature count ≥ 2 |
| `prism.escalation` | (routing) | severity / notify targets for the mock webhook |

Aggregated by `prism.trip.decision`. Tested with `opa test policies/rego -v`
(independent of Python). YAML under `src/.../policies/default_policies.yaml`
only sizes the FSM buffer + cooldown — **not** trip thresholds.

## Policy engine modes (ADR-001 local-only)

1. **HTTP** — `PRISM_OPA_URL` → Compose `opa` service (`:9113`).
2. **CLI eval** — local `opa eval` against `PRISM_OPA_POLICY_DIR` (unit tests).
3. **Unavailable** — fail-**open** on trips (never invent a trip), `/health`
   reports `policy_engine.ready: false` (ADR-005). No silent YAML fallback.

## API

- `POST /v1/observations` — `{asset_id, kind, detail}`
- `GET /breakers` / `GET /breakers/{asset_id}`
- `GET /incidents?status=...` / acknowledge / resolve
- `GET /v1/webhook-test/inbox` — mock alerting includes `escalation` from Rego
- `GET /v1/journal`

## Who calls this

`ingestion`, `cv-service`, and `drift-monitor` report observations best-effort
(fail-open if this service is down).
