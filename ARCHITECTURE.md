# PRISM architecture

PRISM is a visual fleet-intelligence platform: edge telemetry and imagery flow into a Databricks lakehouse, CV findings enrich the silver/gold layers, and a single activation contract fans gold data into Redshift and Snowflake. A Django control plane and Vue 3 + Three.js cockpit sit on top; an AI copilot answers only from tool calls.

## System diagram

```mermaid
flowchart LR
  subgraph Edge["Fleet Edge"]
    Cams["Fleet cameras + sensors (simulated)"]
  end
  Cams --> Kinesis["Kinesis Data Streams"]
  Kinesis --> S3Raw["S3 raw zone (bronze)"]
  S3Raw --> CV["cv-service\n(OpenCV + ONNX/YOLO)"]
  CV --> S3Raw
  S3Raw --> DBX["Databricks + PySpark\n(Lakeflow Declarative Pipelines)"]
  DBX --> Silver["Silver (Delta/Iceberg, Unity Catalog)"]
  Silver --> DBT["dbt Core models"]
  DBT --> Gold["Gold (Delta/Iceberg, Unity Catalog)"]
  Gold --> Activation["activation-gateway\n(unified warehouse contract)"]
  Activation --> Redshift["Redshift Serverless"]
  Activation --> Snowflake["Snowflake\n(Horizon Catalog, zero-copy)"]
  Gold -.->|"DR mirror"| Azure["Azure Databricks + ADLS Gen2"]
  Redshift --> API["control-plane\n(Django + Django Ninja)"]
  Snowflake --> API
  API --> RDS["RDS Postgres (Multi-AZ)"]
  API --> Cockpit["cockpit\nVue 3 + Three.js digital twin"]
  Activation --> Copilot["ai-copilot\n(tool-grounded, non-fabricating)"]
  Copilot --> Cockpit
  ALB["ALB + WAF"] --> API
  ALB --> Cockpit
  ALB --> CV
```

## Layers

| Layer | Technology | Role |
|---|---|---|
| Ingestion | Kinesis (+ local shim) | Fleet camera frames + sensor pings |
| Object storage | S3 | Raw zone, table storage, static assets |
| Lakehouse | Databricks (PySpark, Unity Catalog, Lakeflow Declarative Pipelines) | Bronze → silver → gold |
| Modeling | dbt Core | Silver → gold tests, docs, lineage |
| Serving WH #1 | Redshift Serverless | Gold activation (zero-ETL / auto-copy) |
| Serving WH #2 | Snowflake Horizon Catalog | Iceberg zero-copy read |
| DR | Azure Databricks + ADLS Gen2 | Warm-standby mirror |
| CV | OpenCV + ONNX Runtime (YOLO-family) | Defect / anomaly detection |
| Control plane | Django 5.x + Django Ninja | Assets, work orders, review, RBAC |
| Frontend | Vue 3 + Three.js WebGPURenderer | Digital-twin cockpit |
| Copilot | Tool-grounded NL service | Ask PRISM — no fabrication |
| Compute | ECS Fargate + Service Connect | Stateless services |
| OLTP | RDS PostgreSQL Multi-AZ | Control-plane store |
| IaC | Terraform | AWS platform modules (Phase 6); Azure DR Phase 7; plan/validate/checkov in CI only |

## Contracts

Cross-service schemas live under `contracts/` and are imported, never copied:

- `telemetry-schema` — `SensorPing` + `CameraFrameMetadata` (Pydantic + JSON Schema)
- `cv-finding-schema` — `CvFinding` defect/anomaly findings (Pydantic + JSON Schema; emitter in Phase 3)
- `activation-contract` — warehouse-agnostic activate/query OpenAPI (`POST /v1/activate`, `POST /v1/query`)

## Ingestion path (Phase 1)

Mock fleet simulator → contract gate → stream producer (`file` default or LocalStack Kinesis) → Hive-partitioned bronze zone under `.data/bronze/{sensor_pings|camera_frames}/dt=…/device=…/`. Rejected events land in `.data/bronze/_dlq/`.

## Lakehouse path (Phase 2)

Bronze JSON → PySpark silver (typed, expectation-filtered, deduped) → gold aggregates, written as parquet under `.data/lakehouse/{silver,gold}/`.  
Data-quality expectations live in `lakehouse/quality/expectations.yaml` and are applied as Unity Catalog table properties (`quality.expectation.*`) via `unity_catalog/bootstrap.sql` (manual workspace apply). Lakeflow Declarative Pipelines reference those property keys.  
dbt Core models silver→gold for analytics tests (DuckDB in CI; Databricks SQL warehouse profile documented for real runs).

## Computer vision path (Phase 3)

Fleet frames → `cv-service` (OpenCV preprocess + ONNX YOLO-family, CPU) → schema-valid `CvFinding` records.  
Findings with `confidence < threshold` land in `.data/cv-review-queue/pending/` for human review (Phase 5); higher-confidence findings publish under `.data/cv-findings/published/`. No GPU / paid vision APIs in CI (ADR-001).

## Activation path (Phase 4)

Gold parquet (S3 or local) → `activation-gateway` (`:9103`) behind `activation-contract`:

- **Redshift adapter** — zero-ETL / auto-copy preferred; COPY from Parquet/Iceberg fallback → `materialized_copy`
- **Snowflake adapter** — Iceberg REST / Horizon Catalog zero-copy against the **same** gold URI → `zero_copy` (no storage duplication)
- **Routing registry** — `warehouse=auto` queries the current primary; callers may pin a warehouse for failover / conformance
- **Conformance suite** — identical SQL against both mocked warehouse endpoints (`:9110` / `:9111`); assert equivalent results

Why both warehouses: [ADR-002](docs/adr/002-multi-warehouse-activation.md).

## Control plane path (Phase 5)

`cv-service` low-confidence findings → `.data/cv-review-queue/pending/` → Django control plane (`:9100`):

- Sync/list reads the **same pending JSON files** cv-service writes
- `viewer` / `inspector` / `fleet-admin` RBAC on the Ninja API
- Approve / reject / relabel → `ReviewDecision` + `AuditLogEntry`; pending file → `decided/`
- Approved/relabeled → lakehouse gold (`.data/lakehouse/gold/cv_findings/`, `reviewed=true`) via Django-Q2 (inline on SQLite)

## AWS platform path (Phase 6)

Terraform under `infra/terraform/aws/` (validate / tflint / checkov / plan only — never apply in CI or by agents):

- Multi-AZ VPC (public / private / isolated), NAT, flow logs, S3 + CloudWatch VPC endpoints
- ALB + WAFv2 with path-based routing to Fargate services; Service Connect for east-west calls
- RDS PostgreSQL Multi-AZ (encrypted, isolated subnets, IAM DB auth)
- S3 raw/gold (CMK) with raw `bronze/` → Glacier lifecycle; dedicated SSE-S3 access-logs bucket for ALB
- Secrets Manager + least-privilege per-task IAM (explicit SIDs / ARNs)
- CloudWatch Container Insights, ops dashboard, alarms (5xx / latency / queue depth)

Local `docker compose` remains the day-to-day path; Terraform does not replace it.

## Cost safety

See [ADR-001](docs/adr/001-cost-safety-policy.md). Local path uses Docker Compose + emulators (DuckDB, LocalStack, moto, mock warehouses, SQLite). CI validates Terraform and uploads a reviewable AWS plan artifact; humans apply.

## Build order

Phases 0 → 11 are documented in the build brief and tracked via `PHASE_N_COMPLETION.md` files at the repo root. Phase 0 scaffolds the monorepo, rules, CI, contract stubs, and empty Terraform roots only.
