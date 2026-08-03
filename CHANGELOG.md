# Changelog

All notable changes to PRISM are documented here.

## [Unreleased]

## [1.1.0] — 2026-08-03 — Chaos/audit core (Phases 12–15)

See [docs/RELEASE_PLAN.md](docs/RELEASE_PLAN.md).

### Phase 15 — Cockpit Breaker Board + scenario controls + copilot tools

- `scenario-engine`: `POST /v1/reset` — in-process seed change, no container restart
- `ingestion`: `POST /v1/scenario-runs` — admin-triggered, bounded, real batch through an isolated pipeline instance
- `ai-copilot`: `query_breakers` / `query_incidents` grounded tools (ADR-004)
- `cockpit`: `BreakerBoard.vue`, `ScenarioControls.vue`; breaker state folded into the twin's health-glow material and the asset detail panel; incident-replay scrubber reused (new `"breaker"` event kind), not duplicated

### Phase 14 — Per-source circuit breaker + incident-engine

- `incident-engine/` on `:9108` — per-asset closed → open → half-open FSM, declarative trip policies (`quarantine_rate`, `consecutive_qa_failures`, dormant `drifted_features`)
- `ingestion`/`cv-service` report observations best-effort, fail-open; a tripped breaker forces all of that asset's cv-service findings to human review
- `GET /breakers`, `GET /incidents`, `POST /incidents/{id}/acknowledge|resolve`, `GET /v1/journal`, mock webhook + inbox

### Phase 13 — Two-layer Pydantic → Pandera validation hardening

- Pydantic triage (per-event) followed by a Pandera batch gate before bronze promotion
- `pyproject.toml` pytest `pythonpath` fallback fixed to cover every service's `src/`

### Phase 12 — Scenario engine (v1.1.0 track)

- `scenario-engine/` on `:9107` — seeded outcomes, append-only audit journal
- `PRISM_SOURCE_MODE=live|scenario` on ingestion (scenario pulls via HTTP)
- Telemetry schema: optional `synthetic_scenario` / `scenario_id` / `scenario_outcome`
- [ADR-005](docs/adr/005-earned-evidence-policy.md) earned-evidence honesty bar

## [1.0.0] — 2026-08-02 — Full portfolio close-out (Phases 0–11)

First tagged release. **`v1.0.0` covers Phases 0–11** (not the earlier mid-build
plan that would have split 0–5 / 6–7 / 8–9 / 10–11 across minors). See
[docs/RELEASE_PLAN.md](docs/RELEASE_PLAN.md).

### Release packaging

- Apache-2.0 `LICENSE` (same as Vulcan / aegis)
- Phase completion docs moved to `docs/phases/PHASE_00`…`PHASE_11_COMPLETION.md`
- GHCR images under `ghcr.io/hamidmatiny/prism/*` tagged `v1.0.0` / `1.0.0` / `latest`

### Phase 11 — Productionization & demo

- End-to-end golden-path test (`tests/e2e`) + CI compose job after all prior gates
- `make demo` seed/dataset stands the full stack up locally in under five minutes
- Finalized ARCHITECTURE.md, four ADRs, DEMO_SCRIPT.md; committed cockpit screenshots

### Phase 10 — Observability & security

- OpenTelemetry (`prism-otel`) through all ECS-bound services + local collector `:9106`
- Per-service CloudWatch LES dashboards/alarms; ReviewQueueDepth EMF from control-plane
- Secrets Manager 30-day rotation (closes Phase 6 `CKV2_AWS_57` deferral)
- IAM least-privilege audit + WAF OWASP Top 10 review (SQLi + IP reputation rules)
- Load test script + recorded results for activation-gateway + cockpit API surface

### Phase 9 — AI copilot (Ask PRISM)

- Tool-grounded `ai-copilot` on `:9104` (warehouse / CV findings / work orders)
- ADR-004 non-fabrication; structural grounding tests; light I/O validation
- Cockpit Ask PRISM panel

### Phase 8 — Digital twin cockpit

- Vue 3 / Vite / Pinia cockpit on `:9101` with dark design system + a11y
- WebGPU twin (WebGL fallback), TSL health materials, incident scrubber
- Wired to control-plane + activation-gateway real API shapes

### Phase 7 — Azure DR layer

- ADLS Gen2 + Azure Databricks warm-standby Terraform (`infra/terraform/azure/`)
- Replication job definition with RPO 15m / RTO 4h targets
- Failover runbook + ADR-003 (two-cloud cost vs DR benefit)
- `make phase7-check` matches CI validate/tflint/checkov parity

### Phase 6 — AWS platform (Terraform)

- Modules under `infra/terraform/aws/`: VPC, ALB+WAF, ECS Fargate + Service Connect, RDS, S3, KMS, Secrets, IAM, observability
- CI: `terraform validate` + tflint + checkov; AWS `terraform plan` uploaded as artifact (mock credentials; never apply)
- Local `docker compose` path unchanged (additive IaC only)

### Phases 0–5 (included)

Data spine + control plane from the pre-tag track — contracts, ingest, lakehouse/dbt,
CV, activation gateway, Django control plane. See [0.5.0](#050--2026-08-01--phase-5-control-plane)
notes below for the Phase 5 cut detail.

## [0.5.0] — 2026-08-01 — Phase 5 (control plane)

*Pre-tag track marker in changelog only — first git tag is `v1.0.0`.*

### Phase commits (0–5)

| Phase | Summary |
|------:|---------|
| 0 | Monorepo scaffold, ADR-001, CI skeleton |
| 1 | Telemetry/CV contracts, fleet simulator, bronze ingest |
| 2 | Spark medallion, UC expectations, dbt Core silver→gold |
| 3 | OpenCV + ONNX CV service, confidence-gated review queue |
| 4 | Activation gateway — Redshift + Snowflake adapters + conformance |
| 5 | Django 5 + Ninja control plane — RBAC review of live CV queue |

### Phase 5 — Control plane

- Models: Asset, WorkOrder, InspectionFinding, ReviewDecision, AuditLogEntry
- Reads real `cv-review-queue/pending/` files from cv-service
- Approve / reject / relabel → gold findings `reviewed=true` (Django-Q2)
- Roles: viewer, inspector, fleet-admin; Postgres via `DATABASE_URL`, SQLite fallback

### Phase 4 — Activation gateway

- OpenAPI activate/query contract; dual adapters; mock warehouses in CI
- ADR-002: why both Redshift and Snowflake
- Live-gold conformance documented vs fixture CI path

### Phase 3 — Computer vision service

- OpenCV preprocess + ONNX YOLO-family (CPU); label set documented
- Low-confidence → human-review queue (no auto-action)

### Phase 2 — Lakehouse

- PySpark bronze→silver→gold; Unity Catalog expectation props; dbt Core (DuckDB CI)

### Phase 1 — Ingestion & contracts

- `SensorPing` / `CameraFrameMetadata` / `CvFinding` contracts
- Simulator + file/LocalStack producer → Hive bronze

### Phase 0 — Foundation

- Cursor rules, ADR-001 cost-safety, Terraform validate-only CI, port map 9100–9199
