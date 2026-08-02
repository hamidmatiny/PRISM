# ADR 002 — Support both Redshift and Snowflake behind one activation contract

**Status:** Accepted (finalized Phase 11)  
**Date:** 2026-08  
**Phases:** 4+

## Context

PRISM's namesake property is that a single governed gold table can be *activated*
into more than one analytical warehouse without inventing a second source of
truth. Enterprise fleet customers already have warehouse investments:

- Some standardize on **Amazon Redshift** (often next to the AWS lakehouse / S3
  gold zone) and expect zero-ETL or auto-copy style serving.
- Others standardize on **Snowflake**, increasingly via **Horizon Catalog /
  Iceberg REST** zero-copy reads against the same S3 tables.

Picking a single warehouse would force a subset of tenants to duplicate gold
data, rewrite BI, or abandon existing spend commitments — undermining the
"prism" thesis.

## Decision

1. Keep **one OpenAPI activation contract** (`contracts/activation-contract`)
   with two operations as first-class peers:
   - activate gold table X into warehouse Y
   - query table X regardless of which warehouse currently serves it
2. Implement **two adapters** in `activation-gateway/`:
   - **Redshift** — prefer zero-ETL / auto-copy from the S3 gold zone; fall back
     to `COPY` from Parquet/Iceberg. Storage mode: `materialized_copy`.
   - **Snowflake** — Iceberg REST / Horizon Catalog **zero-copy** registration
     against the same gold URI. Storage must **not** be duplicated.
3. Maintain a routing registry so `warehouse=auto` queries hit the current
   primary without callers hard-coding a vendor.
4. Prove adapter parity with a **conformance suite** that runs the same SQL
   against both mocked warehouse endpoints and asserts equivalent results
   (Vulcan serving/common discipline applied to warehouses). CI never talks to
   real Redshift/Snowflake (ADR-001).

## Why not pick one

| Option | Why rejected |
|--------|----------------|
| Redshift only | Excludes Snowflake-native tenants; forces Snowflake shops to re-platform BI |
| Snowflake only | Excludes Redshift-centric AWS estates already wired to S3 zero-ETL |
| Dual-write ETL into both with copied storage | Breaks zero-copy economics; two mutable copies drift |
| Lowest-common-denominator SQL engine only | Loses warehouse-native features customers already paid for |

## Cost / latency tradeoffs (workload-shaped, not invented absolutes)

These are **qualitative** tradeoffs to guide routing — not CI-asserted dollar or
ms figures (no fabricated throughput numbers):

| Workload shape | Prefer | Rationale |
|----------------|--------|-----------|
| High-churn operational dashboards already on Redshift | Redshift (`materialized_copy` / zero-ETL) | Keeps serving next to existing Redshift consumption + IAM |
| Multi-cloud / Snowflake-native BI on shared Iceberg gold | Snowflake (`zero_copy`) | Avoids second storage bill; catalog points at the same S3 gold |
| Cross-warehouse audit / failover | Activate both; query via contract | Conformance suite guarantees logical equivalence; primary route is swappable |

Benchmarking real $/query and p95 latency is a **manual, human-triggered**
exercise against paid warehouses outside CI (see ADR-001). Results belong in
runbooks when measured — never hard-coded as claims in tests.

## Consequences

**Gains**

- Multi-tenant customers keep warehouse investments.
- One gold contract for control-plane, cockpit, and copilot.
- Explicit storage-mode distinction prevents accidental dual materialization on
  the Snowflake path.

**Trade-offs (accepted)**

- Two adapters to maintain; conformance tests are mandatory for query-affecting
  changes.
- Real cost/latency numbers are out-of-band; CI proves equivalence only.
- Some SQL dialect differences may require gateway normalization over time.

## Compliance checklist

- [ ] New warehouse features go through `activation-contract` first.
- [ ] Snowflake path remains zero-copy against the shared gold URI.
- [ ] Conformance tests cover activate + identical SELECT for both adapters.
- [ ] No real Redshift/Snowflake credentials in default CI (ADR-001).
