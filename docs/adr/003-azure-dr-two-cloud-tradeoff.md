# ADR 003 — Azure warm-standby DR vs two-cloud operational cost

**Status:** Accepted (revisit at production scale)  
**Date:** 2026-08  
**Phases:** 7+

## Context

PRISM’s primary path is AWS: S3 lakehouse, ECS services, RDS, and
activation-gateway into Redshift and/or Snowflake. The Phase 0 architecture
sketch named **Azure Databricks + ADLS Gen2** as a warm-standby DR mirror so
enterprise questionnaires could point at a “second cloud” story.

Building that mirror is cheap in Terraform lines and expensive in everything
else. This ADR weighs the **ongoing** cost of a second cloud against the DR
benefit for a project that is still portfolio-stage — not a live multi-tenant
fleet with contractual RTO.

## What a second cloud actually costs

Even as a warm standby (not active-active), Azure DR adds a permanent surface:

| Surface | What you keep paying / staffing |
|---------|----------------------------------|
| **Second Databricks workspace** | Workspace SKU, metastore/admin identity, job definitions, cluster policies, upgrade cadence |
| **ADLS Gen2 storage** | Mirrored gold (+ optional bronze/silver), versioning/soft-delete, access policies |
| **Ongoing replication job** | Scheduled compute every RPO interval, S3 egress, failure alerts, credential rotation for cross-cloud read |
| **Doubled ops / security** | Entra ID + Azure RBAC next to AWS IAM; second secrets store; second billing account; second place to misconfigure public access; runbooks and drills |
| **Cognitive load** | On-call must know two providers; incidents span two consoles; “is gold fresh on Azure?” becomes a standing question |

Warm standby is cheaper than hot dual-write. It is **not** free, and most months
you pay for a copy you never serve.

## What DR benefit you actually get

| Benefit | Honest scope |
|---------|----------------|
| Second-provider copy of gold | Useful if AWS S3/region is unavailable **and** someone runs the failover runbook |
| Analytics continuity | Possible via activation-gateway → Snowflake / Databricks SQL against `abfss://` gold |
| RFP / board checkbox | “We have a documented Azure warm standby” |

| Non-benefit | Why |
|-------------|-----|
| Automatic failover | Cutover is human-gated (hours, not seconds) |
| Redshift continuity | Redshift does not run on Azure; that adapter stays down |
| Full platform DR | control-plane, CV, ingestion remain AWS-native in this design |
| Substitute for AWS resilience | Multi-AZ, S3 versioning, and backups still do the real work day-to-day |

Default targets if the mirror is kept: **RPO ≈ 15 minutes** (job cadence),
**RTO ≈ 4 hours** (manual procedure in
[azure-dr-failover.md](../runbooks/azure-dr-failover.md)).

## Decision

**For the current portfolio-stage build, the tradeoff is marginal.**

We still ship the Azure Terraform modules and runbook so the architecture
sketch is not a fiction, and so a future production push has something concrete
to enable. We do **not** treat Azure DR as a justified standing production
expense today.

Practical stance:

1. **Code exists; spend is optional.** Validate/tflint/checkov in CI (ADR-001).
   Humans apply Azure only when a real drill or customer requirement pays for it.
2. Prefer **AWS-region DR / backups** as the default resilience story until
   production traffic and contracts demand a second cloud.
3. If Azure is applied, keep it **warm standby + manual failover** — never market
   it as multi-cloud HA.
4. **Revisit** when any of these become true: contractual RTO/RPO with customers,
   sustained production analytics revenue, or a buyer who hard-requires
   second-provider DR in writing.

An honest future outcome of that revisit is “turn the Azure footprint off and
delete the subscription resources.” That is allowed. This ADR is not obligated
to justify the cloud we scaffolded.

## Alternatives considered

| Option | Assessment now |
|--------|----------------|
| No Azure DR at all | Best cost fit for portfolio stage; weaker second-provider story |
| Scaffold only (this phase) | Documents the design; spend stays zero until apply — **chosen** |
| Applied warm standby with live replication | Justified when drills/contracts pay for the doubled surface |
| Hot active-active dual cloud | Rejected — roughly doubles cost and ops for little portfolio-stage gain |
| AWS second-region only | Often the better *first* production DR move; one cloud to operate |

## Consequences

- Docs must say **optional warm standby**, not “we run multi-cloud HA.”
- activation-gateway failover steps live in the runbook; Redshift is explicitly
  out of scope during an AWS outage.
- If nobody schedules a yearly tabletop, the scaffold is documentation — and
  that may be the correct amount of DR for this stage.

## References

- [ADR-001](001-cost-safety-policy.md) — no apply / no paid APIs in CI  
- [ADR-002](002-multi-warehouse-activation.md) — warehouse activation contract  
- [azure-dr-failover.md](../runbooks/azure-dr-failover.md)  
- `infra/terraform/azure/`
