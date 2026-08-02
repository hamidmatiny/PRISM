# Phase 6 completion — AWS platform (Terraform)

**Date:** 2026-08-02  
**Status:** Complete (awaiting human go-ahead before Phase 7)

## What shipped

Terraform modules under `infra/terraform/aws/` for the PRISM AWS platform:

| Module | Contents |
|--------|----------|
| `kms` | Platform CMK with rotation for logs, secrets, S3 data zones, RDS |
| `vpc` | Multi-AZ public / private / isolated subnets, NAT per AZ, flow logs, S3 + CloudWatch interface endpoints, default SG locked |
| `alb_waf` | Public ALB, HTTPS (TLS1.3 policy), HTTP→HTTPS redirect, path rules per service, WAFv2 (Common + KnownBadInputs + AnonymousIp) + logging, access logs |
| `ecs` | Fargate services for ingestion, cv-service, activation-gateway, control-plane, ai-copilot; Service Connect; Container Insights; scoped task SG egress |
| `rds` | PostgreSQL 16 Multi-AZ, encrypted (CMK), isolated subnets, IAM DB auth, Performance Insights (CMK), enhanced monitoring |
| `s3` | Raw + gold (SSE-KMS) with raw `bronze/` → Glacier after N days; dedicated SSE-S3 access-logs bucket (ALB constraint) |
| `secrets` | Secrets Manager for RDS master + app runtime (CMK) |
| `iam` | Execution role + **per-task** roles with explicit SIDs and resource ARNs (ECR `GetAuthorizationToken` is the only intentional `Resource=*`) |
| `observability` | Ops dashboard + alarms (ALB 5xx, p95 latency, RDS CPU, control-plane task count, review-queue depth) |

CI (`terraform` + `terraform-aws-plan` jobs): `validate` + `tflint` + `checkov` on aws/azure; **AWS `terraform plan` uploaded as `aws-terraform-plan` artifact**. No `terraform apply` anywhere.

Local `docker compose` path is unchanged — Terraform is additive.

## Verified

| Check | Result |
|-------|--------|
| `terraform init -backend=false && terraform validate` (aws) | Success |
| `tflint --format compact` (aws) | Clean |
| `checkov -d infra/terraform/aws --config-file …/.checkov.yml` | **300 passed / 0 failed** (1 justified skip: logs bucket SSE-S3 for ALB) |
| `terraform plan` with mock example credentials + local backend | **Plan: 123 to add**; `tfplan.txt` reviewable |
| Azure scaffold validate / tflint / checkov | Success (null Phase-0 stack) |
| `docker compose` services already up | control-plane `:9100`, cv-service `:9102`, activation-gateway `:9103`, ingestion `:9105`, foundation-stub `:9199` — healthy |

## Explicit non-claims / hard rules

- **No `terraform apply`** was run. No real AWS credentials were used. Plan used documented example keys + provider credential skips.
- Plan is a **review artifact**, not a green light to provision.
- Secret rotation Lambdas, S3 CRR, and multi-region DR remain deferred (Phase 7+).
- Review-queue depth alarm expects custom metric `PRISM/ReviewQueueDepth` (emitter wiring is ops/Phase 10).

## Local vs CI checkov discrepancy (fixed)

Initial Phase 6 push reported local checkov **300/0**, then GitHub Actions failed with **10** findings.

**Cause:** `.github/workflows/ci.yml` passed `skip_check: CKV_TF_1` into `bridgecrewio/checkov-action`. Checkov CLI precedence means `--skip-check` **replaces** the entire `skip-check` list from `.checkov.yml`, so the documented suppressions never applied in CI. Local `make`/CLI used `--config-file` only → green.

**Fix:** CI and `make checkov-aws` share one pinned invocation (`infra/terraform/CHECKOV_VERSION` + `--config-file` only, no CLI `--skip-check`). Unit test `test_ci_checkov_does_not_override_yaml_skips` guards the gap. Skip ledger: `infra/terraform/aws/CHECKOV_SKIPS.md` + inline `#checkov:skip=` reasons on resources.

## Justified checkov skips

See `infra/terraform/aws/CHECKOV_SKIPS.md`. Highlights: HTTP `:80` redirect-only, HTTP TGs behind TLS ALB, CRR/event notifications deferred to Phase 7/ops, secret rotation deferred (CMK-encrypted), ALB SSE-S3 log destination.

## How to verify

```bash
cd infra/terraform/aws
terraform init -backend=false && terraform validate
tflint --init && tflint --format compact
checkov -d . --framework terraform --config-file .checkov.yml --compact --quiet
make terraform-aws-plan   # mock keys only — writes tfplan.txt
# Do NOT run terraform apply
curl -sS http://localhost:9100/health
curl -sS http://localhost:9102/health
curl -sS http://localhost:9103/health
```

## Stop

Phase 6 only. Do not start Phase 7 until explicitly requested.
