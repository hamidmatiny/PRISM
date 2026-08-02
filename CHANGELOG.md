# Changelog

All notable changes to PRISM are documented here.

## [Unreleased]

### Phase 6 — AWS platform (Terraform)

- Modules under `infra/terraform/aws/`: VPC, ALB+WAF, ECS Fargate + Service Connect, RDS, S3, KMS, Secrets, IAM, observability
- CI: `terraform validate` + tflint + checkov; AWS `terraform plan` uploaded as artifact (mock credentials; never apply)
- Local `docker compose` path unchanged (additive IaC only)

### Housekeeping

- Release plan (`docs/RELEASE_PLAN.md`), packaging plan (`docs/PACKAGING_PLAN.md`)
- Repo description / topics aligned with shipped phases (0–5)

## [0.5.0] — 2026-08-01 — Phase 5 (control plane)

*Pre-v1.0.0 track — not yet tagged `v1.0.0`.*

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
