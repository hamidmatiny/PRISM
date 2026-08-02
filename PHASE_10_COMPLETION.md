# Phase 10 completion — Observability & security

**Date:** 2026-08-02  
**Status:** Complete (awaiting human go-ahead before Phase 11)

## What shipped

- Shared `prism-otel` package + local OTel collector on **:9106**; wired into
  every ECS-bound service (ingestion, cv-service, activation-gateway,
  control-plane, ai-copilot). Cockpit propagates W3C `traceparent` on fleet
  refresh so ingest→API→render correlation is inspectable in
  `.data/otel/traces.json`.
- CloudWatch **per-service** LES dashboards (latency / errors / saturation) and
  alarms with sane thresholds; fleet ops dashboard retained; ReviewQueueDepth
  EMF emitter on control-plane review-queue reads.
- **IAM least-privilege audit** of every Phase 6 Terraform role —
  [docs/security/iam-least-privilege-audit.md](docs/security/iam-least-privilege-audit.md)
- **WAF vs OWASP Top 10** review + SQLi / Amazon IP reputation managed rules —
  [docs/security/waf-owasp-top10-review.md](docs/security/waf-owasp-top10-review.md)
- **Secrets rotation** Lambda + `aws_secretsmanager_secret_rotation` (30-day) —
  closes Phase 6 `CKV2_AWS_57` deferral explicitly
  ([docs/runbooks/secrets-rotation.md](docs/runbooks/secrets-rotation.md))
- Basic load test against activation-gateway + cockpit API surface —
  [observability/load-tests/RESULTS.md](observability/load-tests/RESULTS.md)

## Verified

| Check | Result |
|-------|--------|
| Unit tests (82) incl. Phase 10 OTel / CKV2_AWS_57 closed | Green locally |
| `terraform validate` (aws) + archive provider | Green locally |
| `checkov` aws — 358 passed, 0 failed; **no `CKV2_AWS_57` skip** | Green locally |
| OTel file export: `activation-gateway` + `control-plane` in `.data/otel/traces.json` | Green |
| Load test 8×40 — 0% errors on gateway + cockpit API surface | Green ([RESULTS.md](observability/load-tests/RESULTS.md)) |
| `cockpit` typecheck | Green |
| GitHub Actions for this commit | Linked after push |

## Test it yourself

```bash
# Stack + collector
docker compose up -d --build otel-collector activation-gateway control-plane cockpit

# Prove traces land locally
curl -sS -H 'traceparent: 00-aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa-bbbbbbbbbbbbbbbb-01' \
  http://127.0.0.1:9103/health >/dev/null
sleep 2
# Expect service.name activation-gateway (and siblings after traffic) in:
ls -la .data/otel/ && wc -c .data/otel/traces.json

# Load test (cockpit proxy + gateway + control-plane)
TOKEN=$(docker compose exec -T control-plane python manage.py print_api_token viewer)
python observability/load-tests/run_load_test.py --token "$TOKEN"
cat observability/load-tests/RESULTS.md

# Secrets rotation loop closed (no CKV2_AWS_57 skip)
rg CKV2_AWS_57 infra/terraform/aws/.checkov.yml  # expect no match
rg aws_secretsmanager_secret_rotation infra/terraform/aws/modules/secrets/rotation.tf
```

## Explicit non-claims

- No `terraform apply`; CloudWatch / Secrets Manager rotation are plan-validated.
- RDS `ALTER ROLE` inside rotation `setSecret` is apply-time (VPC + runbook).
- Load test is a basic concurrency probe, not a capacity certification.

## Stop

Phase 10 only. Do not start Phase 11 until explicitly requested.
