# observability

Phase 10 — OpenTelemetry + CloudWatch LES dashboards/alarms + local load tests.

| | |
|---|---|
| **OTLP HTTP (host)** | **9106** → collector `:4318` |
| **Trace dump** | `.data/otel/traces.json` (compose volume) |
| **Shared SDK** | `observability/otel` (`prism-otel`) |
| **Load tests** | `observability/load-tests/run_load_test.py` |

## Local collector

```bash
docker compose up -d otel-collector
# Services export when OTEL_EXPORTER_OTLP_ENDPOINT=http://otel-collector:4318
```

Cockpit sends W3C `traceparent` on control-plane / activation / copilot fetches
(`cockpit/src/lib/trace.ts`) so a fleet-refresh can be correlated end to end.

## AWS (plan-only)

- Per-service CloudWatch dashboards + CPU / latency / 5xx alarms:
  `infra/terraform/aws/modules/observability/`
- Secrets rotation (closes `CKV2_AWS_57`):
  `infra/terraform/aws/modules/secrets/rotation.tf` +
  [docs/runbooks/secrets-rotation.md](../docs/runbooks/secrets-rotation.md)
- IAM audit: [docs/security/iam-least-privilege-audit.md](../docs/security/iam-least-privilege-audit.md)
- WAF / OWASP: [docs/security/waf-owasp-top10-review.md](../docs/security/waf-owasp-top10-review.md)

## Load test

```bash
TOKEN=$(docker compose exec -T control-plane python manage.py print_api_token viewer)
python observability/load-tests/run_load_test.py --token "$TOKEN"
```

Results: `observability/load-tests/RESULTS.md` (and `last-run.json`).
