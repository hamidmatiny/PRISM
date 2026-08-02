# Architecture Decision Records

Short records of the biggest technology choices in PRISM. Each ADR states the context, decision, and consequences.

Every `NNN-*.md` ADR in this directory **must** appear in the table below (enforced by `tests/unit/test_foundation.py`).

| ID | Title | Status |
|----|-------|--------|
| [001](001-cost-safety-policy.md) | Cost-safety policy (CI never touches real cloud / paid APIs / GPU) | Accepted |
| [002](002-multi-warehouse-activation.md) | Support both Redshift and Snowflake behind one activation contract | Accepted |
| [003](003-azure-dr-two-cloud-tradeoff.md) | Azure warm-standby DR vs two-cloud operational cost | Accepted (revisit at production scale) |
| [004](004-copilot-non-fabrication.md) | Ask PRISM tool-grounded non-fabrication (no invented numbers) | Accepted |
| [005](005-earned-evidence-policy.md) | Earned-evidence policy (no unearned capability / readiness claims) | Accepted |

ADRs 001–004 closed the v1.0.0 portfolio; ADR-005 opens the v1.1 honesty bar for chaos / drift / incidents. New ADRs should be added here before implementation diverges.
