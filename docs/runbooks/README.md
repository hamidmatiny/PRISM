# Runbooks

Operational procedures for PRISM.

| Runbook | Phase | Status |
|---------|------:|--------|
| [Azure DR failover](azure-dr-failover.md) — repoint activation-gateway at ADLS gold | 7 | Written |
| Warehouse switch (Redshift ↔ Snowflake via activation-gateway) | 4 / 7 | Covered in activation-gateway README + ADR-002; full switch runbook may expand later |
| Incident response | 10 | Pending |

Related ADRs: [ADR-003](../adr/003-azure-dr-two-cloud-tradeoff.md) (why Azure DR may stay unapplied at portfolio stage).
