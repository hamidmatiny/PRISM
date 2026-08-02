# AWS platform (Terraform)

Phase 6 modules for PRISM on AWS. **Validate / plan only in CI** — [ADR-001](../../../docs/adr/001-cost-safety-policy.md).

## Modules

| Module | Purpose |
|--------|---------|
| `kms` | Platform CMK (rotation on) for logs, secrets, S3 data zones, RDS |
| `vpc` | Multi-AZ public / private / isolated subnets, NAT, flow logs, S3 + CloudWatch VPC endpoints |
| `alb_waf` | ALB + WAFv2 + path-based routing to ECS services |
| `ecs` | Fargate services + Service Connect + Container Insights |
| `rds` | PostgreSQL Multi-AZ, encrypted, isolated subnets |
| `s3` | Raw + gold (CMK) + access-logs (SSE-S3 for ALB); raw `bronze/` → Glacier after N days |
| `secrets` | Secrets Manager for RDS + app runtime |
| `iam` | Least-privilege execution + per-task roles (no wildcard policies) |
| `observability` | Dashboard + alarms (5xx, latency, RDS CPU, queue depth) |

## Local validation (no apply)

```bash
cd infra/terraform/aws
terraform init -backend=false
terraform validate
tflint --init && tflint
# Plan with mock credentials only — never real keys in automation:
AWS_ACCESS_KEY_ID=AKIAIOSFODNN7EXAMPLE \
AWS_SECRET_ACCESS_KEY=wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY \
AWS_EC2_METADATA_DISABLED=true \
terraform plan -input=false -lock=false -out=tfplan.binary
terraform show -no-color tfplan.binary > tfplan.txt
```

## Apply (humans only)

1. Review CI plan artifact.
2. Set real `aws_account_id`, AZs, `alb_certificate_arn`, and turn off skip flags.
3. Configure a remote backend out-of-band.
4. Run `terraform apply` from a trusted workstation — **never from GitHub Actions or Cursor agents**.
