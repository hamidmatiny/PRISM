# ADR 001 — Cost-safety policy

**Status:** Accepted (finalized Phase 11)  
**Date:** 2026-08  
**Phases:** 0+ (all phases)

## Context

PRISM spans AWS (Kinesis, S3, ECS, RDS, Redshift Serverless), Databricks, Snowflake, Azure DR (Databricks + ADLS Gen2), and optional GPU/ONNX vision inference. Accidental CI or agent automation against any of those surfaces can create recurring cloud spend and is hard to reverse mid-PR.

Sibling projects already treat production-shaped infra as **validate-in-CI, apply-out-of-band** (Argus) and forbid GPU spend in automation (Vulcan ADR-002). PRISM must adopt the same bar across warehouses, multi-cloud DR, and CV inference.

## Decision

### CI and automation (hard rules)

1. **CI never provisions real cloud infrastructure** and never calls paid cloud / SaaS APIs as part of the default PR matrix.
2. **CI never runs GPU inference** or paid vision/LLM endpoints. CV and copilot tests use fixtures, CPU ONNX (when introduced), or mocks.
3. **Terraform is validate-only in CI:**
   - Allowed: `terraform init` (no remote backend required for validate), `terraform validate`, `tflint`, `checkov`, and optionally `terraform plan` as a review artifact.
   - Forbidden: `terraform apply` in GitHub Actions or any Cursor-driven automation.
4. **Warehouse and AWS access in tests** use local emulators or structural checks only:
   - DuckDB for warehouse SQL semantics
   - LocalStack for AWS-shaped APIs
   - moto for boto3 unit tests
5. **`terraform apply` is a manual, human-triggered step** outside CI and outside agent control, after plan review.

### Local development

- `docker compose up` / `make up` bring up a usable path with **zero cloud credentials**.
- Cloud credentials are optional overlays documented per service; they must never be required for the local demo.

### Reference in later phases

Every phase that touches cloud services, warehouses, or GPU/CV inference must cite this ADR and keep a validate-only / emulator path in CI.

## Alternatives considered

| Option | Why not |
|--------|---------|
| Nightly apply-to-dev from CI | Still recurring spend; easy to expand accidentally; surprises cost owners |
| “Plan-only except main” apply | Merge-to-main apply still violates the explicit human gate |
| Mock-only with no local SQL/AWS shim | Misses contract and adapter bugs that DuckDB/LocalStack/moto catch cheaply |

## Consequences

**Gains**

- Predictable CI cost; no surprise cloud invoices from PRs or agents.
- Contributors can iterate on contracts and services on a laptop without accounts.
- Infra PRs still get structural validation (validate / tflint / checkov).

**Trade-offs (accepted)**

- Real warehouse latency/cost characteristics are **not** proven in CI — they require manual runs documented in runbooks/benchmarks.
- Azure DR and Databricks workspace wiring are structurally validated until a human applies them.
- Contributors need discipline: never “just add” live cloud credentials to the default workflow.

## Compliance checklist (reviewers)

- [ ] No workflow step creates AWS/Azure/Databricks/Snowflake/Redshift resources.
- [ ] No `terraform apply` (or cloud CLI create/update) in Actions.
- [ ] Tests that touch “AWS” or “warehouses” use LocalStack, moto, DuckDB, or structural fixtures.
- [ ] CV / copilot CI paths do not require GPU or paid API keys.
- [ ] New cloud-touching phases reference this ADR.
