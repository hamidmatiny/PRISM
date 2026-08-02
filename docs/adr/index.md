# Architecture Decision Records

Short records of the biggest technology choices in PRISM. Each ADR states the context, decision, and consequences.

| ID | Title | Status |
|----|-------|--------|
| [001](001-cost-safety-policy.md) | Cost-safety policy (CI never touches real cloud / paid APIs / GPU) | Accepted |
| [002](002-multi-warehouse-activation.md) | Support both Redshift and Snowflake behind one activation contract | Accepted |
| [003](003-azure-dr-two-cloud-tradeoff.md) | Azure warm-standby DR vs two-cloud operational cost | Accepted (revisit at production scale) |
| [004](004-copilot-non-fabrication.md) | Ask PRISM tool-grounded non-fabrication (no invented numbers) | Accepted |

All four are finalized as of Phase 11. New ADRs should be added here before implementation diverges.
