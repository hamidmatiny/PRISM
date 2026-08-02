# PRISM

**Visual Fleet Intelligence & Multi-Warehouse Analytics Platform.**

PRISM ingests fleet camera + sensor telemetry, runs computer-vision defect/anomaly detection, lands governed gold data in a Databricks lakehouse (dbt-modeled), and fans that same gold layer out to Redshift and Snowflake through one activation contract — surfaced in a Django control plane and a Vue 3 + Three.js digital-twin cockpit, with a tool-grounded AI copilot over live warehouse data.

> One gold table, split into many warehouses — like a prism splitting light.

## Status

| Phase | Component | Status |
|-------|-----------|--------|
| 0 | Foundation | Complete — see `PHASE_0_COMPLETION.md` |
| 1 | Ingestion & contracts | Complete — see `PHASE_1_COMPLETION.md` |
| 2 | Lakehouse core | Complete — see `PHASE_2_COMPLETION.md` |
| 3 | Computer vision service | Complete — see `PHASE_3_COMPLETION.md` |
| 4 | Activation gateway | Complete — see `PHASE_4_COMPLETION.md` |
| 5 | Control plane | Not started |
| 6 | AWS platform | Not started |
| 7 | Azure DR layer | Not started |
| 8 | Digital twin cockpit | Not started |
| 9 | AI copilot | Not started |
| 10 | Observability & security | Not started |
| 11 | Productionization & demo | Not started |

## Quick start (Phase 4)

```bash
cp .env.example .env
python3 -m venv .venv && source .venv/bin/activate
pip install -e contracts/activation-contract -e activation-gateway
docker compose up -d --build activation-gateway
curl -s http://localhost:9103/health
GOLD_URI="file://$(pwd)/activation-gateway/fixtures/gold/asset_daily_metrics"
curl -s http://localhost:9103/v1/activate -H 'content-type: application/json' \
  -d "{\"gold_table\":\"asset_daily_metrics\",\"warehouse\":\"redshift\",\"gold_uri\":\"$GOLD_URI\"}"
curl -s http://localhost:9103/v1/query -H 'content-type: application/json' \
  -d '{"table":"asset_daily_metrics","warehouse":"auto","sql":"SELECT asset_id, ping_count FROM asset_daily_metrics ORDER BY asset_id"}'
```

No cloud credentials / real warehouses required ([ADR-001](docs/adr/001-cost-safety-policy.md), [ADR-002](docs/adr/002-multi-warehouse-activation.md)).

## Monorepo layout

```
prism/
├── .cursor/rules/              # Contract-first + cost-safety rules
├── .github/workflows/          # CI: lint, test, terraform validate/tflint/checkov
├── contracts/                  # Shared schemas (telemetry, CV, activation)
├── ingestion/                  # Simulator + producer + bronze landing
├── cv-service/                 # OpenCV + ONNX YOLO defects (CPU)
├── lakehouse/                  # PySpark medallion + Lakeflow + UC bootstrap
├── dbt/                        # dbt Core silver→gold (DuckDB CI)
├── activation-gateway/         # Redshift + Snowflake behind one contract
├── control-plane/              # Phase 5
├── ai-copilot/                 # Phase 9
├── cockpit/                    # Phase 8
├── infra/terraform/{aws,azure} # Phases 6 / 7 (scaffold validates now)
├── observability/              # Phase 10
├── docs/adr/                   # ADRs
├── docker-compose.yml
├── Makefile
├── ARCHITECTURE.md
└── README.md
```

## Host ports

PRISM owns **9100–9199** (avoids Argus / Vulcan on shared laptops).

| Port | Service |
|------|---------|
| 9100 | control-plane |
| 9101 | cockpit |
| 9102 | cv-service (live) |
| 9103 | activation-gateway (live; mocks on 9110/9111) |
| 9104 | ai-copilot |
| 9105 | ingestion |
| 9199 | Phase 0 foundation stub |

## Engineering bar

1. **Contract-first** — schemas live in `contracts/`; services import, never duplicate.
2. **ADRs** for real decisions — [ADR-001 cost safety](docs/adr/001-cost-safety-policy.md), [ADR-002 multi-warehouse](docs/adr/002-multi-warehouse-activation.md).
3. **Cost safety** — CI never applies Terraform, never calls paid APIs, never runs GPU inference. Emulators only (DuckDB, LocalStack, moto).
4. **Phase discipline** — one phase at a time; each ends with `PHASE_N_COMPLETION.md`.
5. **Local-first** — `docker compose up` works without cloud credentials.

## Docs

- [ARCHITECTURE.md](ARCHITECTURE.md)
- [ADRs](docs/adr/index.md)
- [Demo script](docs/DEMO_SCRIPT.md) (Phase 11)
- [Phase 0 completion](PHASE_0_COMPLETION.md)
- [Phase 1 completion](PHASE_1_COMPLETION.md)
- [Phase 2 completion](PHASE_2_COMPLETION.md)
- [Phase 3 completion](PHASE_3_COMPLETION.md)
- [Phase 4 completion](PHASE_4_COMPLETION.md)
