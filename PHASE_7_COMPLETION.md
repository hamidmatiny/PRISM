# Phase 7 completion — Azure DR layer

**Date:** 2026-08-02  
**Status:** Complete (awaiting human go-ahead before Phase 8)

## What shipped

- Terraform under `infra/terraform/azure/` replacing the Phase-0 null scaffold:
  - ADLS Gen2 storage account (HNS) with bronze / silver / gold containers
  - Azure Databricks workspace (`standard` SKU default — warm standby)
  - Replication **job definition** (Jobs API JSON) + notebook source for S3 → ADLS mirror
- Documented **RPO = 15 minutes** (job cron) and **RTO = 4 hours** (manual failover) as Terraform outputs / variables
- Runbook: [`docs/runbooks/azure-dr-failover.md`](docs/runbooks/azure-dr-failover.md) — how to repoint activation-gateway at the Azure gold mirror (Redshift explicitly does not fail over)
- ADR: [`docs/adr/003-azure-dr-two-cloud-tradeoff.md`](docs/adr/003-azure-dr-two-cloud-tradeoff.md) — honest cost vs benefit of two clouds
- Checkov ledger: `infra/terraform/azure/CHECKOV_SKIPS.md` + `.checkov.yml`
- README **Test it yourself** section with CI-identical commands
- `make phase7-check` = lint + unit tests + terraform validate + tflint + checkov for **both** stacks (same work CI's terraform matrix does)

## Verified

| Check | Result |
|-------|--------|
| `terraform init -backend=false && terraform validate` (azure) | Success |
| `tflint` (azure, azurerm ruleset) | Clean |
| `make checkov-azure` (pinned checkov, config-file only) | Green |
| `make phase7-check` | Green (matches CI terraform + lint + test surface) |
| GitHub Actions run for this commit | Linked in commit notes / chat after push |

## Explicit non-claims / hard rules

- **No `terraform apply`** and **no real Azure subscription** used.
- No Azure `terraform plan` in CI — azurerm plan needs a live SP; validate/tflint/checkov only.
- Warm standby ≠ multi-cloud HA. Failover is human-gated.
- Replication notebook is a structural wire-up; production apply may swap in Delta CLONE / `dbutils.fs.cp`.

## Local ↔ CI parity

Same discipline as the Phase 6 checkov fix:

- Pinned `infra/terraform/CHECKOV_VERSION`
- CI and `make checkov-azure` share `--config-file …/.checkov.yml` with **no** CLI `--skip-check`
- `make phase7-check` also runs `tflint` for aws + azure like the workflow matrix

## Stop

Phase 7 only. Do not start Phase 8 until explicitly requested.
