# IAM least-privilege audit — Phase 6 Terraform roles (Phase 10)

Source of truth: `infra/terraform/aws/modules/iam/main.tf` (+ secrets rotation role
in `modules/secrets/rotation.tf`).

## Roles inventoried

| Role | Purpose |
|------|---------|
| `{prefix}-ecs-execution` | ECR pull, Secrets Manager inject at task start, awslogs |
| `{prefix}-task-ingestion` | Bronze S3 write, app secret read |
| `{prefix}-task-cv-service` | Raw frames read, findings write |
| `{prefix}-task-activation-gateway` | Gold read, app secret |
| `{prefix}-task-control-plane` | Gold findings R/W, RDS + app secrets |
| `{prefix}-task-ai-copilot` | Gold read, app secret |
| `{prefix}-secrets-rotation` | Rotate RDS + app secrets (Phase 10) |

## Findings

### Broader than ideal (documented, accepted)

| Finding | Why broader | Mitigation / why accepted |
|---------|-------------|---------------------------|
| `ecr:GetAuthorizationToken` on `Resource=*` (execution role) | AWS API is account-scoped; cannot ARN-scope | Companion `EcrPullPrismImages` statement limits pulls to `repository/prism-*`. Checkov `CKV_AWS_111` skipped with ledger reason. |
| `secretsmanager:GetRandomPassword` on `*` (rotation role) | AWS requires `*` for this action | Used only by rotation Lambda; no secret data access beyond explicit ARNs. |
| Rotation Lambda log ARN uses wildcard suffix | Log group name includes function name prefix | Scoped to `/aws/lambda/{prefix}-secrets-rotation*`. |
| `kms:Decrypt` on platform CMK for multiple task roles | Single platform key for secrets + logs | Key policy + IAM both required; no plaintext secret in env beyond ECS injection. |
| control-plane S3 `ListBucket` on whole gold bucket | ListBucket is bucket-level | Object R/W still prefix-scoped to findings / review-queue paths. |

### Tight (no change needed)

| Role | Notes |
|------|-------|
| ingestion | Bronze prefix-only writes; no gold read |
| cv-service | Frames prefix read; findings/review-queue write only |
| activation-gateway | Gold read only — no PutObject |
| ai-copilot | Gold read only — matches read-only tools (ADR-004) |
| Per-task log ARNs | Each task role writes only its own `/ecs/{prefix}/{service}` stream |

### Gaps closed / residual ops

| Item | Status |
|------|--------|
| No `Action: "*"` or `Resource: "*"` on data-plane statements (except AWS-mandated) | Pass |
| Cross-service secret access (e.g. ingestion reading RDS) | Not granted |
| Rotation role could `PutSecretValue` only on the two PRISM secrets | Pass |
| Future: split CMKs (logs vs secrets) | Optional harden; not required for Phase 10 |

## Verdict

IAM is **least-privilege for the Phase 6 service graph**. The only intentional
`Resource=*` grants are AWS-mandated API shapes, each paired with a scoped
companion statement and recorded in `CHECKOV_SKIPS.md`.
