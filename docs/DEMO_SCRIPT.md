# PRISM demo script

Placeholder — finalized in Phase 11.

Intended golden path (for orientation only):

1. Simulated fleet event lands via ingestion.
2. CV service emits a schema-valid finding.
3. Low-confidence findings enter the control-plane review queue; an inspector approves.
4. Gold layer updates; activation-gateway serves the same answer from Redshift and Snowflake adapters (local emulators in demo).
5. Cockpit digital twin shows the asset + defect overlay; Ask PRISM answers from tool calls only.
