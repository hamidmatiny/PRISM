# ai-copilot

Tool-grounded **Ask PRISM** natural-language query service (Phase 9).

| | |
|---|---|
| **Port (host)** | `9104` |
| **Health** | `GET /health` |
| **Ask** | `POST /v1/ask` |
| **ADR** | [ADR-004](../docs/adr/004-copilot-non-fabrication.md) |

## Contract

Every factual number or claimable id in an answer must appear in that turn’s
tool evidence. If it can’t be grounded, the copilot says so — it does not
guess. Default path uses deterministic templates (no paid LLM; ADR-001).

### Tools

| Tool | Backend |
|------|---------|
| `query_warehouse` | activation-gateway `POST /v1/query` |
| `query_cv_findings` | control-plane review-queue + findings + gold dir |
| `query_work_orders` | control-plane `GET /api/v1/work-orders` |

Light-touch validation only (prompt-injection heuristics + PII redaction).
Full policy engines belong in **aegis**, not here.

## Test it yourself

```bash
# From repo root — backends + copilot
docker compose up -d --build control-plane control-plane-worker \
  activation-gateway cv-service ai-copilot

TOKEN=$(docker compose exec -T control-plane python manage.py print_api_token viewer)
curl -sS http://127.0.0.1:9104/health

# Warehouse telemetry (numbers must match activation-gateway rows)
curl -sS http://127.0.0.1:9104/v1/ask -H 'content-type: application/json' \
  -d "{\"question\":\"What are the ping_count values from warehouse telemetry?\",\"control_plane_token\":\"$TOKEN\"}" \
  | python3 -m json.tool

# CV findings (pending_count from live review-queue)
curl -sS http://127.0.0.1:9104/v1/ask -H 'content-type: application/json' \
  -d "{\"question\":\"How many CV findings are pending review?\",\"control_plane_token\":\"$TOKEN\"}" \
  | python3 -m json.tool

# Work orders
curl -sS http://127.0.0.1:9104/v1/ask -H 'content-type: application/json' \
  -d "{\"question\":\"How many open work orders are there?\",\"control_plane_token\":\"$TOKEN\"}" \
  | python3 -m json.tool
```

**What grounded answers look like**

- Telemetry: cites `redshift`/`snowflake`, `asset_daily_metrics`, and each
  `ping_count` that appeared in `/v1/query` rows for that turn.
- CV: cites `pending_count` / `findings_count` / `gold_count` and optional
  `finding_id` / `defect_class` / `confidence` from the queue payload.
- Work orders: cites `total` and `open` counts from control-plane.
- Response always includes `tool_calls` + `evidence` so you can verify
  grounding by eye (same check CI runs structurally).

### In the cockpit

```bash
cd cockpit && npm run dev
# open http://localhost:9101 → Use token → click Ask PRISM
```

## Local (no compose)

```bash
pip install -e ai-copilot
export PRISM_ACTIVATION_URL=http://127.0.0.1:9103
export PRISM_CONTROL_PLANE_URL=http://127.0.0.1:9100
export PRISM_CONTROL_PLANE_TOKEN="$TOKEN"
python -m prism_ai_copilot
```
