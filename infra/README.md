# infra

Terraform for AWS platform (Phase 6) and Azure DR (Phase 7).

```
infra/terraform/aws/     # VPC, ALB+WAF, ECS, RDS, S3, IAM, CloudWatch
infra/terraform/azure/   # Databricks + ADLS Gen2 warm standby + replication job
```

## Cost safety (ADR-001)

- CI: `terraform validate`, `tflint`, `checkov` only (AWS also uploads a mock-credential plan artifact).
- `terraform apply` is **manual and human-run** — never from Actions or agents.
- Local gates: `make phase6-check` / `make phase7-check` mirror CI flags (no silent skip overrides).

## Docs

- Azure DR failover: [`docs/runbooks/azure-dr-failover.md`](../docs/runbooks/azure-dr-failover.md)
- Two-cloud tradeoff: [`docs/adr/003-azure-dr-two-cloud-tradeoff.md`](../docs/adr/003-azure-dr-two-cloud-tradeoff.md)
