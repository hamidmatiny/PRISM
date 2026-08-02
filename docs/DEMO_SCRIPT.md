# PRISM demo script

**Audience:** hiring / partner walkthrough (≈12 minutes talk track; stack boots via `make demo` in under five).  
**Cost safety:** local Docker only — no cloud credentials ([ADR-001](adr/001-cost-safety-policy.md)).

## 0. Boot (operator, before the room)

```bash
git clone https://github.com/hamidmatiny/PRISM.git && cd PRISM
make demo
# prints viewer token + URLs; budget ≤ 300s
```

Open **http://127.0.0.1:9101**, paste the viewer token, click **Use token**.

Optional proof of the full pipeline (same path CI e2e runs):

```bash
PRISM_E2E=1 pytest -q tests/e2e -m e2e
```

## 1. Fleet twin (cockpit)

- Point at the dark **PRISM** shell and the 3D asset floor.
- Asset glow is driven by **open work orders + unreviewed CV findings** from the control plane — not a painted legend.
- Click **PRISM-AST-001** → detail panel: telemetry bars (activation-gateway), CV frame overlay, work orders.

**Say:** “Same gold metrics the warehouses serve are what the twin charts.”

## 2. Ingest → CV → human review

```bash
# One simulated fleet event into bronze
docker compose -f docker-compose.yml -f docker-compose.demo.yml \
  exec -T ingestion python -c \
  'from prism_ingestion.config import IngestConfig; from prism_ingestion.pipeline import IngestPipeline; p=IngestPipeline.from_config(IngestConfig.from_env()); print(p.process_one())'

# Force a finding into the review queue (demo compose uses threshold 0.99)
curl -sS -X POST http://127.0.0.1:9102/v1/detect \
  -F asset_id=PRISM-AST-001 \
  -F frame_ref=frm_$(openssl rand -hex 6) \
  -F file=@cv-service/fixtures/images/dent_sample.png | python3 -m json.tool | head

TOKEN=$(docker compose exec -T control-plane python manage.py print_api_token inspector)
curl -sS -H "Authorization: Bearer $TOKEN" http://127.0.0.1:9100/api/v1/review-queue | python3 -m json.tool | head
```

Approve one pending finding in the API (or show the queue in the UI after refresh):

```bash
FID=<finding_id from queue>
curl -sS -X POST -H "Authorization: Bearer $TOKEN" -H 'content-type: application/json' \
  -d '{"decision":"approve","notes":"demo"}' \
  "http://127.0.0.1:9100/api/v1/review-queue/${FID}/decide"
ls .data/lakehouse/gold/cv_findings/${FID}.json
```

**Say:** “Low-confidence CV never silently becomes gold — an inspector signs it.”

## 3. One gold table → Redshift and Snowflake

```bash
GOLD="file:///data/lakehouse/gold/asset_daily_metrics"
curl -sS http://127.0.0.1:9103/v1/activate -H 'content-type: application/json' \
  -d "{\"gold_table\":\"asset_daily_metrics\",\"warehouse\":\"redshift\",\"gold_uri\":\"$GOLD\",\"set_primary\":true}"
curl -sS http://127.0.0.1:9103/v1/activate -H 'content-type: application/json' \
  -d "{\"gold_table\":\"asset_daily_metrics\",\"warehouse\":\"snowflake\",\"gold_uri\":\"$GOLD\",\"set_primary\":false}"

SQL='SELECT asset_id, ping_count FROM asset_daily_metrics WHERE asset_id = '"'"'PRISM-AST-001'"'"''
curl -sS http://127.0.0.1:9103/v1/query -H 'content-type: application/json' \
  -d "{\"table\":\"asset_daily_metrics\",\"warehouse\":\"redshift\",\"sql\":\"$SQL\"}"
curl -sS http://127.0.0.1:9103/v1/query -H 'content-type: application/json' \
  -d "{\"table\":\"asset_daily_metrics\",\"warehouse\":\"snowflake\",\"sql\":\"$SQL\"}"
```

**Say:** “Same contract, two warehouses — [ADR-002](adr/002-multi-warehouse-activation.md). Local mocks stand in for Serverless/Horizon; the contract is what ships.”

## 4. Ask PRISM

In the cockpit **Ask PRISM** panel (or):

```bash
VIEWER=$(docker compose exec -T control-plane python manage.py print_api_token viewer)
curl -sS http://127.0.0.1:9104/v1/ask -H 'content-type: application/json' \
  -d "{\"question\":\"What CV findings and work orders exist for PRISM-AST-001?\",\"control_plane_token\":\"$VIEWER\"}" \
  | python3 -m json.tool
```

Expect `grounded: true` and citations that appear in `evidence` / tool payloads — [ADR-004](adr/004-copilot-non-fabrication.md).

## 5. Ops / DR one-liners (no live cloud)

- Observability: OTel collector on `:9106`, traces under `.data/otel/`; CloudWatch LES dashboards in Terraform (plan-only).
- DR: Azure warm-standby modules + failover runbook — [ADR-003](adr/003-azure-dr-two-cloud-tradeoff.md), `docs/runbooks/azure-dr-failover.md`. Emphasize **cost vs benefit**, not theater.

## Screenshots

Committed captures from a live `make demo` session: [docs/screenshots/](screenshots/).

## Cleanup

```bash
docker compose -f docker-compose.yml -f docker-compose.demo.yml down
```
