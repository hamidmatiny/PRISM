# Checkov skip ledger (AWS Terraform)

Machine-readable skips live in [`.checkov.yml`](.checkov.yml) and as
`#checkov:skip=<ID>: <reason>` comments on the owning resources.

**Rule:** every skip here must have a written reason. Silent skips are not allowed.
**Rule:** CI must invoke checkov with `--config-file .checkov.yml` only — never also
pass `--skip-check` / `skip_check:` (CLI overrides wipe the YAML skip list).

Pinned version: **checkov 3.3.8** (Makefile + CI).

| Check ID | Resource(s) | Decision | Reason |
|----------|-------------|----------|--------|
| `CKV_TF_1` | local modules | suppress | Sources are `./modules/*`, not remote git refs with version pins. |
| `CKV_AWS_260` | `alb_waf.aws_security_group.alb` | suppress | Public `:80` exists only so the HTTP listener can 301-redirect to HTTPS. Closing `:80` removes the redirect path; TLS still terminates on `:443`. |
| `CKV_AWS_378` | `alb_waf.aws_lb_target_group.service` | suppress | Target groups are HTTP to private Fargate tasks; TLS terminates at the ALB (HTTPS listener + WAF). |
| `CKV_AWS_2` | ALB HTTP listener | suppress (global) | HTTP listener is redirect-only; HTTPS listener is the real edge. |
| `CKV2_AWS_28` | ALB HTTP listener | suppress (global) | Same redirect-only HTTP listener pattern. |
| `CKV_AWS_144` | `s3` raw/gold/logs | suppress | Cross-region replication is Phase 7 (Azure DR warm standby), not a single-region AWS scaffold concern. |
| `CKV2_AWS_62` | `s3` raw/gold/logs | suppress | Event notifications need a real consumer (EventBridge/SQS → lakehouse/jobs). Wiring empty targets is security theater; enable with ops emitters when consumers exist. |
| `CKV_AWS_111` | IAM execution | suppress (global) | `ecr:GetAuthorizationToken` is account-scoped; AWS requires `Resource=*`. Companion statement scopes image pulls. |
| `CKV_AWS_91` | ALB access logs graph | suppress (global) | Access logging is enabled on the ALB to the dedicated SSE-S3 logs bucket; graph check is noisy with module boundaries. |
| `CKV2_AWS_20` | public ALB | suppress (global) | Public ALB is the product edge; WAF + HTTPS protect it. |
| `CKV_AWS_145` | `s3.aws_s3_bucket.logs` | suppress (inline) | ALB access-log delivery does not support SSE-KMS destinations; SSE-S3 is required by AWS. |
| `CKV_AWS_117` | `secrets.aws_lambda_function.rotation` | suppress | Rotation Lambda VPC/SG attachment is apply-time (RDS connectivity). Plan scaffold rotates secret versions; runbook covers VPC join before enabling `PRISM_ROTATION_APPLY_RDS`. |
| `CKV_AWS_116` | rotation Lambda | suppress | DLQ optional for 30-day rotation cadence; Secrets Manager rotation status + CW logs are the failure signal. |
| `CKV_AWS_50` | rotation Lambda | suppress | X-Ray optional; CW logs + SM events provide audit. |
| `CKV_AWS_115` | rotation Lambda | suppress | Reserved concurrency unnecessary for infrequent rotation invocations. |
| `CKV_AWS_272` | rotation Lambda | suppress | Code signing deferred; zip is built from this module’s `lambda/rotate.py`. |

**Resolved (not skipped):** `CKV2_AWS_57` and `CKV_AWS_149` are **absent** from
`.checkov.yml` `skip-check` and from the table above. Rotation attachments are on
`aws_secretsmanager_secret.{rds,app}` via `aws_secretsmanager_secret_rotation` in
`modules/secrets/main.tf` (Lambda in `rotation.tf`). See
`docs/runbooks/secrets-rotation.md`.

## Local ↔ CI parity

```bash
# Same command CI runs (from repo root):
checkov -d infra/terraform/aws \
  --config-file infra/terraform/aws/.checkov.yml \
  --framework terraform \
  --compact --quiet
```

`make phase6-check` includes this invocation. Do not add a second `skip_check` input in
`.github/workflows/ci.yml`.
