# Runbook — Fail over activation-gateway to the Azure lakehouse mirror

**Audience:** human operator (never CI / never agents)  
**Related:** [ADR-003](../adr/003-azure-dr-two-cloud-tradeoff.md), `infra/terraform/azure/`, `activation-gateway/`  
**Targets (if mirror is live):** RPO ≈ **15 minutes** · RTO ≈ **4 hours**

## Goal

Keep **analytics reads** working when AWS S3 gold (or the AWS activation path)
is unavailable, by serving gold from the **ADLS Gen2 mirror** and telling
activation-gateway to stop preferring Redshift.

## What breaks in the meantime

Until failover completes — and partially even after:

| Broken / degraded | Why |
|-------------------|-----|
| **Redshift activate/query** | AWS-only. No Azure equivalent. Mark degraded; do not route `warehouse=auto` there. |
| **Freshness** | Mirror lags by up to RPO; post-failover numbers may be minutes behind last AWS gold. |
| **Writes / new gold** | Ingestion + lakehouse on AWS should be paused to avoid split-brain. No new gold until failback or a deliberate Azure write path (out of scope). |
| **control-plane, CV, review queue** | Still on AWS. This runbook does **not** move OLTP or CV. |
| **Callers hard-coded to Redshift** | They fail until they use `warehouse=snowflake` / `auto` after you flip primary. |

## Preconditions

1. Azure DR was **actually applied** (human `terraform apply`) and the
   replication job has been running.
2. You can read:
   - `gold_abfss_uri` → `abfss://gold@<storage>.dfs.core.windows.net/`
   - Databricks workspace URL / job run history
3. You can change activation-gateway config and restart it (ECS task definition
   or local compose).
4. Snowflake (or Databricks SQL behind the Snowflake-shaped adapter path) is
   reachable for DR serving.

If Azure was never applied (portfolio default per ADR-003), **stop** — there is
nothing to fail over to. Restore AWS or accept analytics downtime.

---

## Failover procedure

### 1. Declare and freeze writes (~15 min)

1. Incident channel: “AWS analytics → Azure gold mirror failover started.”
2. Pause ingestion / lakehouse jobs that publish to AWS gold.
3. Note start time (RTO clock).

### 2. Confirm the mirror is good enough (~30–60 min)

1. Databricks → Jobs → `prism-<env>-lakehouse-mirror` → last **successful** run.
2. Lag must be ≤ RPO (default 15m). If worse, run the job once manually or
   **abort** (serving stale gold can be worse than waiting on AWS).
3. Spot-check at least one critical table under the gold container (e.g.
   `asset_daily_metrics` partition date / row count sanity).

### 3. Repoint activation-gateway at Azure gold (~30–60 min)

activation-gateway chooses gold from, in order:

1. Activate request field `gold_uri`, or
2. `PRISM_ACTIVATION_GOLD_ROOT` + table name (`config.resolve_gold_uri`), and
3. Routing primary in `PRISM_ACTIVATION_ROUTING_PATH`
   (default `.data/activation/routing.json`) when callers use `warehouse=auto`.

**A. Set gold root to the ADLS mirror**

From the applied Azure stack:

```bash
# Human workstation with state / known outputs — not CI
cd infra/terraform/azure
GOLD_ABFSS="$(terraform output -raw gold_abfss_uri)"
echo "$GOLD_ABFSS"
# example: abfss://gold@prismdevlakedrXXXX.dfs.core.windows.net/
```

ECS / prod task definition (or secrets):

```text
PRISM_ACTIVATION_GOLD_ROOT=<GOLD_ABFSS>
PRISM_ACTIVATION_MODE=<production mode for your deploy — not mock>
# Keep routing file on durable storage:
PRISM_ACTIVATION_ROUTING_PATH=/data/activation/routing.json
```

Redeploy / restart activation-gateway. Confirm:

```bash
curl -sS https://<gateway-host>:9103/health
# expect status ok; note warehouse health map
```

**B. Force primary off Redshift**

Activate Snowflake (or your non-Redshift warehouse) against the mirrored table
and set it primary:

```bash
GATEWAY="https://<gateway-host>:9103"   # or http://localhost:9103 for a drill
GOLD_URI="${GOLD_ABFSS}lakehouse/gold/asset_daily_metrics"
# If your mirror layout is container-root tables, use:
# GOLD_URI="${GOLD_ABFSS}asset_daily_metrics"

curl -sS "$GATEWAY/v1/activate" \
  -H 'content-type: application/json' \
  -d "{
    \"gold_table\": \"asset_daily_metrics\",
    \"warehouse\": \"snowflake\",
    \"gold_uri\": \"${GOLD_URI}\",
    \"set_primary\": true
  }"
```

Confirm routing file / API no longer selects Redshift for `auto`:

```bash
curl -sS "$GATEWAY/v1/warehouses"
# Redshift should look unhealthy or non-primary; Snowflake (or DR target) primary
```

**C. Optional: edit routing state directly**

If activate cannot reach Snowflake yet but you must stop `auto` → Redshift,
update `routing.json` primary warehouse field to `snowflake` (shape owned by
`activation-gateway` routing registry) and restart the gateway. Prefer the
activate API when possible so the registry stays consistent.

### 4. Smoke query (~30 min)

```bash
curl -sS "$GATEWAY/v1/query" \
  -H 'content-type: application/json' \
  -d '{
    "table": "asset_daily_metrics",
    "warehouse": "auto",
    "sql": "SELECT asset_id, ping_count FROM asset_daily_metrics ORDER BY asset_id LIMIT 20"
  }'
```

Pass criteria:

- HTTP 200 with rows (or empty set if table legitimately empty)
- Response warehouse is **not** `redshift`
- Counts/shape match last known good within RPO expectations

### 5. Communicate (~remainder of RTO window)

Tell consumers:

- Analytics are on the **Azure gold mirror**
- **Redshift is down** for the incident
- Data may lag AWS by up to RPO
- Writes remain frozen until failback

---

## Failback (AWS restored)

1. Confirm AWS S3 gold is healthy; lakehouse caught up.
2. **Pause** the Azure mirror job (do not overwrite fresher AWS data if you
   later reverse-sync).
3. Set `PRISM_ACTIVATION_GOLD_ROOT` back to the AWS gold root
   (e.g. `s3://<prism-*-gold>/lakehouse/gold/` or your standard URI).
4. Restart activation-gateway.
5. Re-activate preferred warehouses and restore primary:

```bash
# Example: put Redshift back as primary if that is your steady state
curl -sS "$GATEWAY/v1/activate" -H 'content-type: application/json' -d "{
  \"gold_table\": \"asset_daily_metrics\",
  \"warehouse\": \"redshift\",
  \"gold_uri\": \"s3://<aws-gold-bucket>/lakehouse/gold/asset_daily_metrics\",
  \"set_primary\": true
}"
# Optionally keep Snowflake activated with set_primary: false (ADR-002)
```

6. Smoke `warehouse=auto` query again; confirm Redshift (or chosen primary).
7. Resume Azure mirror job for warm standby.
8. Resume ingestion / lakehouse writers.
9. Write down actual RPO lag and RTO elapsed; patch this runbook if steps lied.

---

## Local drill note (no real Azure)

`PRISM_ACTIVATION_MODE=mock` maps `s3://` to `.data/` and does **not** speak
real `abfss://`. A full Azure failover drill needs human Azure credentials and
is out of CI (ADR-001). Structural validation of the Terraform + this runbook:

```bash
make phase7-check
test -f docs/runbooks/azure-dr-failover.md
test -f docs/adr/003-azure-dr-two-cloud-tradeoff.md
```

## Explicit non-goals

- Automated DNS flip with no human
- Failing over control-plane / CV / ingestion to Azure
- Promising Redshift availability during an AWS outage
