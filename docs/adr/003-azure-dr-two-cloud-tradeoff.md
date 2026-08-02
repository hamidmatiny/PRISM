# ADR 003 — Azure warm-standby DR vs two-cloud operational cost

**Status:** Accepted  
**Date:** 2026-08  
**Phases:** 7+

## Context

PRISM's primary lakehouse and activation path run on **AWS** (S3 medallion, ECS
services, RDS, Redshift/Snowflake activation). Enterprise RFPs often ask for a
**documented DR story** outside the primary cloud. The Phase 0 architecture
named **Azure Databricks + ADLS Gen2** as a warm standby.

Running two clouds is not free — in money or attention. This ADR records the
tradeoff honestly so we neither under-build DR nor pretend a second cloud is
"basically free insurance."

## Decision

1. Keep a **warm-standby** Azure footprint (Databricks workspace + ADLS Gen2),
   not a hot active-active dual write.
2. Replicate lakehouse zones on a **scheduled job** (default every **15 minutes**
   → **RPO ≈ 15m**). Failover is **human-gated** (runbook RTO target **≈ 4h**).
3. Treat Azure DR as **optional capacity you pay for continuity theater that
   can become real**, not as a second production control plane.
4. Accept that **Redshift does not fail over to Azure**. DR serving goes through
   activation-gateway repointed at the ADLS gold URI (Snowflake Iceberg and/or
   Databricks SQL), per [azure-dr-failover.md](../runbooks/azure-dr-failover.md).

## Cost of two clouds (what you actually pay)

| Cost type | Warm standby (this design) | Hot dual-cloud (rejected) |
|-----------|----------------------------|---------------------------|
| ADLS storage | ~1× gold (+ optional bronze) on **LRS** | Full multi-region + always-fresh dual write |
| Databricks | Workspace idle + **job clusters** on schedule | Always-on SQL warehouses / interactive clusters |
| Data egress | S3 → internet → Azure on each mirror run | Continuous bidirectional sync |
| IAM / secrets | Extra Entra ID, storage credentials, job SPs | Double every rotation / audit surface |
| People | Runbook drills, two provider skill sets | Two on-call graphs, two billing owners |

Qualitative only — no fabricated $/month in CI (ADR-001). The important claim is
directional: **warm standby is cheaper than active-active, still not free**, and
most months you pay for a mirror you hope never to serve from.

## Benefit (what you actually get)

- A **second cloud** copy of gold for board-level / customer DR questionnaires.
- Ability to serve analytics if AWS region or S3 gold is unavailable, after a
  **manual** cutover measured in hours, not seconds.
- Isolation from a single-provider control-plane outage (Azure Entra + Databricks
  vs AWS IAM + ECS).

What you do **not** get:

- Automatic failover.
- Feature parity for Redshift-native tenants during an AWS outage.
- Zero RPO / near-zero RTO without paying hot-standby prices.
- A substitute for backups, AWS multi-AZ, or S3 versioning — those remain primary.

## Alternatives considered

| Option | Why not (for PRISM now) |
|--------|-------------------------|
| No Azure DR | Fails common enterprise DR checkbox; higher concentration risk |
| Hot active-active on Azure | Roughly doubles platform cost and operational surface; not justified pre-revenue |
| AWS-only DR (second region) | Cheaper ops (one cloud) but fails "second provider" asks some buyers make |
| Cold vault / Glacier-only copy | Meets backup, fails "stand up analytics in hours" RTO |

## Consequences

- Terraform under `infra/terraform/azure/` stays **validate-only in CI**; humans
  apply and import the Databricks job.
- Product docs must say **warm standby + manual failover**, never "multi-cloud HA."
- If DR drills never happen, the spend is largely waste — schedule a yearly
  tabletop using the runbook or drop the Azure footprint.

## References

- [ADR-001](001-cost-safety-policy.md) — no apply / no paid APIs in CI  
- [ADR-002](002-multi-warehouse-activation.md) — activation contract across warehouses  
- [azure-dr-failover.md](../runbooks/azure-dr-failover.md)  
- `infra/terraform/azure/` (RPO/RTO outputs)
