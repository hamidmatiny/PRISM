# Secrets Manager rotation policy (Phase 10)

Closes the Phase 6 `CKV2_AWS_57` deferral: RDS master and app runtime secrets
now have Terraform-defined automatic rotation (30 days) via
`modules/secrets/rotation.tf` + `lambda/rotate.py`.

## Secrets in scope

| Secret | Path | Contents | Rotation cadence |
|--------|------|----------|------------------|
| RDS master | `{prefix}/rds/master` | `username`, `password`, `engine`, `port` | 30 days |
| App runtime | `{prefix}/app/runtime` | `DJANGO_SECRET_KEY`, `PRISM_BOOTSTRAP_PASSWORD` | 30 days |

Both secrets remain CMK-encrypted (`kms_key_id` on the secret resource).

## Rotation handshake

AWS Secrets Manager invokes the Lambda for each step:

1. **createSecret** — write `AWSPENDING` version with a new password / keys.
2. **setSecret** — apply credentials to the dependent system.
3. **testSecret** — validate pending payload is non-empty (extend with DB ping when VPC-joined).
4. **finishSecret** — promote `AWSPENDING` → `AWSCURRENT`.

## Apply-time checklist (human-gated; ADR-001)

1. Attach the rotation Lambda to private subnets + RDS security group (closes `CKV_AWS_117` intent).
2. Set `PRISM_ROTATION_APPLY_RDS=true` and implement / swap in the AWS-provided
   PostgreSQL rotation single-user Lambda **or** extend `set_secret` to run
   `ALTER ROLE prism_admin PASSWORD …` against RDS.
3. After first successful RDS rotation, force a control-plane task restart so
   new `DATABASE_SECRET_JSON` is injected (ECS secrets are resolved at task start).
4. App secret rotation: redeploy ECS services that mount `APP_SECRETS_JSON`
   (or refresh bootstrap tokens via `print_api_token` after password change).
5. Verify CloudWatch log group `/aws/lambda/{prefix}-secrets-rotation` and
   Secrets Manager → Rotation status = Successful.

## Local / CI

No live rotation in CI. `terraform validate` + checkov confirm
`aws_secretsmanager_secret_rotation` exists; `CKV2_AWS_57` is **not** skipped.

## Emergency rotate

```bash
aws secretsmanager rotate-secret --secret-id <arn> --rotation-lambda-arn <lambda-arn>
```

Document the new password in the incident channel; rotate API tokens if
`PRISM_BOOTSTRAP_PASSWORD` changed.
