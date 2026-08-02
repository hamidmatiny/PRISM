# Runbook — Fail over activation-gateway to the Azure lakehouse mirror

**Audience:** on-call / platform operator (human only)  
**Related:** [ADR-003](../adr/003-azure-dr-two-cloud-tradeoff.md), `infra/terraform/azure/`  
**Targets:** RPO ≈ **15 minutes** (mirror job), RTO ≈ **4 hours** (this procedure)

## When to use

AWS S3 gold (or the AWS activation path) is unavailable long enough that serving
analytics from the **Azure ADLS Gen2 mirror** is better than waiting.

Do **not** use this for routine deploys or partial ECS outages that still leave
S3 gold readable.

## What fails over / what does not

| Component | Failover behavior |
|-----------|-------------------|
| Lakehouse **gold** (parquet / tables) | Served from `abfss://gold@<sa>.dfs.core.windows.net/` |
| activation-gateway process | Same binary; **config / routing** change only |
| Snowflake adapter | Prefer: re-activate gold URI on Azure-accessible storage (or Databricks SQL) |
| Redshift adapter | **Does not fail over to Azure.** Mark Redshift degraded; do not pretend. |
| control-plane / CV / ingestion | Out of scope for this runbook (AWS-native). Analytics read path only. |

## Preconditions

1. Azure DR stack applied (`terraform apply` out-of-band — never from CI).
2. Replication job has been succeeding (check Databricks job runs; lag ≤ RPO).
3. You have:
   - `terraform output gold_abfss_uri` (or known ADLS gold URI)
   - ability to restart / reconfigure activation-gateway (ECS task def / compose env)
   - Snowflake or Databricks SQL credentials for DR serving (not Redshift)

## Procedure

### 1. Declare incident and freeze writes (≈ 15 min)

1. Announce AWS → Azure analytics failover in the incident channel.
2. Stop or pause producers that would diverge gold if AWS partially returns
   (ingestion / lakehouse jobs) — avoid split-brain.
3. Record wall-clock start (RTO timer).

### 2. Verify mirror freshness (≈ 30–60 min)

1. Open Azure Databricks workspace (`terraform output databricks_workspace_url`).
2. Confirm last successful `prism-*-lakehouse-mirror` run timestamp ≤ **RPO**.
3. Spot-check critical gold tables under the ADLS gold container (row counts /
   max partition date vs last known good on AWS if still readable read-only).
4. If lag **> RPO**, either wait for a manual job trigger or abort failover
   (stale gold may be worse than downtime).

### 3. Repoint activation-gateway gold (≈ 30–60 min)

activation-gateway resolves gold via env / activate `gold_uri` (see
`activation-gateway` config: `PRISM_ACTIVATION_GOLD_ROOT`, activate request body).

**ECS / prod-shaped:**

1. Set the task definition / secrets so gold reads use the Azure mirror, e.g.
   - `PRISM_ACTIVATION_GOLD_ROOT=<abfss gold path or gateway-supported URI form>`
   - or require callers to pass `gold_uri` = `abfss://gold@<storage>.dfs.core.windows.net/…`
2. Set routing primary away from Redshift:
   - Prefer `warehouse=snowflake` or activate Snowflake against the Azure gold URI
   - Update routing state (`PRISM_ACTIVATION_ROUTING_PATH` / registry) so
     `warehouse=auto` does **not** select Redshift while AWS is down
3. Redeploy activation-gateway; wait for health `GET /health`.

**Local compose (drill only):**

```bash
# Example drill — paths must match your applied outputs
export PRISM_ACTIVATION_GOLD_ROOT="abfss://gold@<storage_account>.dfs.core.windows.net/"
# Force non-Redshift primary for the drill:
curl -sS http://localhost:9103/v1/activate -H 'content-type: application/json' -d "{
  \"gold_table\": \"asset_daily_metrics\",
  \"warehouse\": \"snowflake\",
  \"gold_uri\": \"${PRISM_ACTIVATION_GOLD_ROOT}asset_daily_metrics\",
  \"set_primary\": true
}"
curl -sS http://localhost:9103/health
```

> Mock mode cannot speak real `abfss://`. Drills against real Azure require
> human credentials and are **out of CI** (ADR-001).

### 4. Smoke query (≈ 30 min)

```bash
curl -sS http://localhost:9103/v1/query -H 'content-type: application/json' -d '{
  "table": "asset_daily_metrics",
  "warehouse": "auto",
  "sql": "SELECT asset_id, ping_count FROM asset_daily_metrics ORDER BY asset_id LIMIT 20"
}'
```

Expect `warehouse` ≠ `redshift` while AWS is unavailable. Compare to a known
fixture or last good result set for structural sanity (not bit-identical RPO).

### 5. Communicate and watch (remaining RTO budget)

1. Tell consumers: analytics on Azure mirror; Redshift deactivated; freshness
   may trail by up to RPO.
2. Watch Databricks job + gateway error rates.
3. Do **not** re-enable AWS writers until failback plan is agreed.

## Failback (AWS restored)

1. Confirm AWS S3 gold healthy and lakehouse jobs caught up.
2. Pause Azure mirror job (avoid clobbering fresher AWS data on failback sync).
3. Repoint `PRISM_ACTIVATION_GOLD_ROOT` / activate URIs back to `s3://…`.
4. Restore routing primary (Redshift and/or Snowflake per ADR-002).
5. Resume mirror job for warm standby.
6. Post-incident: note actual RPO lag and RTO elapsed; update this runbook if
   steps were wrong.

## Explicit non-goals

- Automated DNS/traffic flip with no human.
- CV review, control-plane OLTP, or ingestion continuing on Azure.
- Guaranteeing Redshift queries during an AWS outage.
