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
| 5 | Control plane | Complete — see `PHASE_5_COMPLETION.md` |
| 6 | AWS platform | Complete — see `PHASE_6_COMPLETION.md` |
| 7 | Azure DR layer | Complete — see `PHASE_7_COMPLETION.md` |
| 8 | Digital twin cockpit | Complete — see `PHASE_8_COMPLETION.md` |
| 9 | AI copilot | Complete — see `PHASE_9_COMPLETION.md` |
| 10 | Observability & security | Not started |
| 11 | Productionization & demo | Not started |

## Quick start (Phase 5)

```bash
cp .env.example .env
python3 -m venv .venv && source .venv/bin/activate
pip install -e contracts/cv-finding-schema -e control-plane
docker compose up -d --build control-plane control-plane-worker
curl -s http://localhost:9100/health
TOKEN=$(docker compose exec -T control-plane python manage.py print_api_token inspector)
curl -s http://localhost:9100/api/v1/review-queue -H "Authorization: Bearer $TOKEN"
```

No cloud credentials required ([ADR-001](docs/adr/001-cost-safety-policy.md)). Review queue is the real `cv-service` pending directory on the bind-mounted `.data` volume.

## Monorepo layout

```
prism/
├── .cursor/rules/              # Contract-first + cost-safety rules
├── .github/workflows/          # CI: lint, test, terraform validate/tflint/checkov/plan artifact
├── contracts/                  # Shared schemas (telemetry, CV, activation)
├── ingestion/                  # Simulator + producer + bronze landing
├── cv-service/                 # OpenCV + ONNX YOLO defects (CPU)
├── lakehouse/                  # PySpark medallion + Lakeflow + UC bootstrap
├── dbt/                        # dbt Core silver→gold (DuckDB CI)
├── activation-gateway/         # Redshift + Snowflake behind one contract
├── control-plane/              # Django + Ninja review / RBAC / audit
├── ai-copilot/                 # Phase 9
├── cockpit/                    # Phase 8
├── infra/terraform/aws         # Phase 6 platform modules (validate/plan only)
├── infra/terraform/azure       # Phase 7 Azure DR warm standby (validate only)
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
| 9100 | control-plane (live) |
| 9101 | cockpit |
| 9102 | cv-service (live) |
| 9103 | activation-gateway (live; mocks on 9110/9111) |
| 9104 | ai-copilot |
| 9105 | ingestion |
| 9106 | OpenTelemetry collector (OTLP HTTP) |
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
- [Phase 5 completion](PHASE_5_COMPLETION.md)
- [Release plan](docs/RELEASE_PLAN.md) · [Packaging plan](docs/PACKAGING_PLAN.md) · [Changelog](CHANGELOG.md)
