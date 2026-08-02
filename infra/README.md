# infra

Terraform for AWS platform (Phase 6) and Azure DR (Phase 7).

```
infra/terraform/aws/     # VPC, ALB+WAF, ECS, RDS, S3, IAM, CloudWatch
infra/terraform/azure/   # Databricks + ADLS Gen2 warm standby
```

## Cost safety (ADR-001)

- CI: `terraform validate`, `tflint`, `checkov` only.
- `terraform apply` is **manual and human-run** — never from Actions or agents.

## Phase 0

Scaffold roots use the `null` provider so validate works with zero cloud credentials. Real modules replace the scaffold in Phases 6 and 7.
