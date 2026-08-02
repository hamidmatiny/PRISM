# Azure DR layer (Terraform)

Phase 7 warm-standby mirror of the AWS lakehouse: **Azure Databricks** + **ADLS Gen2**.
**Validate / tflint / checkov only in CI** — [ADR-001](../../../docs/adr/001-cost-safety-policy.md).
Tradeoff discussion: [ADR-003](../../../docs/adr/003-azure-dr-two-cloud-tradeoff.md).
Failover steps: [azure-dr-failover.md](../../../docs/runbooks/azure-dr-failover.md).

## Modules

| Module | Purpose |
|--------|---------|
| `resource_group` | DR resource group |
| `adls` | ADLS Gen2 storage account + bronze/silver/gold containers (LRS warm standby) |
| `databricks` | Azure Databricks workspace (`standard` SKU default) |
| `replication` | Jobs API JSON + notebook for S3 → ADLS mirror; **RPO/RTO outputs** |

## RPO / RTO targets

| Metric | Default | Bound by |
|--------|---------|----------|
| **RPO** | **15 minutes** | Databricks job cron (`replication_schedule_cron` = every 15m UTC) |
| **RTO** | **4 hours** | Manual failover runbook (verify lag → repoint activation-gateway → smoke query) |

These are **operational targets**, not CI-asserted SLAs. Adjust via Terraform variables;
keep the runbook and ADR honest if you change them.

## Cost safety

- No real Azure subscription in CI or agent automation.
- No `terraform apply` from Actions / Cursor agents.
- `terraform plan` against Azure is **not** in CI (needs a live SP); humans plan/apply out-of-band.

## Test it yourself

Exact commands matching CI (no apply, no Azure credentials required):

```bash
# From repo root — same pins/flags as .github/workflows/ci.yml
cd infra/terraform/azure
terraform init -backend=false -input=false
terraform validate
tflint --init && tflint --format compact
cd ../../..
make checkov-azure

# Or the full Phase 7 local gate (lint + unit tests + both stacks + tflint + checkov):
make phase7-check
```

Confirm RPO/RTO outputs are wired (after validate-capable init):

```bash
cd infra/terraform/azure
terraform console <<'EOF'
local.rpo_rto
EOF
# Expect rpo_minutes=15, rto_hours=4 (defaults)
```

Read the failover path (no cloud):

```bash
less docs/runbooks/azure-dr-failover.md
less docs/adr/003-azure-dr-two-cloud-tradeoff.md
```

## Apply (humans only)

1. Set real `azure_subscription_id` / `azure_tenant_id` (or `az login` + ARM env).
2. Align `aws_gold_bucket` / `aws_raw_bucket` with the applied AWS stack.
3. `terraform plan` then `terraform apply` from a trusted workstation.
4. Import the replication job: `terraform output -raw replication_job_definition_json > job.json` then `databricks jobs create --json @job.json`.
5. Import `modules/replication/notebooks/mirror_lakehouse.dbx.py` into `/Repos/prism/azure_dr/mirror_lakehouse`.
