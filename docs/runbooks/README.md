# Runbooks

Operational procedures for PRISM.

| Runbook | Phase | Status |
|---------|------:|--------|
| [Azure DR failover](azure-dr-failover.md) — repoint activation-gateway at ADLS gold | 7 | Written |
| [Secrets Manager rotation](secrets-rotation.md) — Lambda rotator, schedule, apply checklist | 10 | Written |
| Warehouse switch (Redshift ↔ Snowflake via activation-gateway) | 4 / 7 | Covered in activation-gateway README + ADR-002; full switch runbook may expand later |
| Incident / security response | 10 | Covered by [IAM audit](../security/iam-least-privilege-audit.md), [WAF/OWASP review](../security/waf-owasp-top10-review.md), and CloudWatch LES alarms (observability module) — dedicated on-call playbook deferred |

Related ADRs: [ADR-003](../adr/003-azure-dr-two-cloud-tradeoff.md) (why Azure DR may stay unapplied at portfolio stage).
