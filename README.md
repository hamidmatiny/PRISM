# PRISM

**Visual Fleet Intelligence & Multi-Warehouse Analytics Platform.**

PRISM ingests fleet camera + sensor telemetry, runs computer-vision defect/anomaly detection, lands governed gold data in a Databricks lakehouse (dbt-modeled), and fans that same gold layer out to Redshift and Snowflake through one activation contract — surfaced in a Django control plane and a Vue 3 + Three.js digital-twin cockpit, with a tool-grounded AI copilot over live warehouse data.

> One gold table, split into many warehouses — like a prism splitting light.

## Status

| Phase | Component | Status |
|-------|-----------|--------|
| 0 | Foundation | Complete — see [`docs/phases/PHASE_00_COMPLETION.md`](docs/phases/PHASE_00_COMPLETION.md) |
| 1 | Ingestion & contracts | Complete — see [`docs/phases/PHASE_01_COMPLETION.md`](docs/phases/PHASE_01_COMPLETION.md) |
| 2 | Lakehouse core | Complete — see [`docs/phases/PHASE_02_COMPLETION.md`](docs/phases/PHASE_02_COMPLETION.md) |
| 3 | Computer vision service | Complete — see [`docs/phases/PHASE_03_COMPLETION.md`](docs/phases/PHASE_03_COMPLETION.md) |
| 4 | Activation gateway | Complete — see [`docs/phases/PHASE_04_COMPLETION.md`](docs/phases/PHASE_04_COMPLETION.md) |
| 5 | Control plane | Complete — see [`docs/phases/PHASE_05_COMPLETION.md`](docs/phases/PHASE_05_COMPLETION.md) |
| 6 | AWS platform | Complete — see [`docs/phases/PHASE_06_COMPLETION.md`](docs/phases/PHASE_06_COMPLETION.md) |
| 7 | Azure DR layer | Complete — see [`docs/phases/PHASE_07_COMPLETION.md`](docs/phases/PHASE_07_COMPLETION.md) |
| 8 | Digital twin cockpit | Complete — see [`docs/phases/PHASE_08_COMPLETION.md`](docs/phases/PHASE_08_COMPLETION.md) |
| 9 | AI copilot | Complete — see [`docs/phases/PHASE_09_COMPLETION.md`](docs/phases/PHASE_09_COMPLETION.md) |
| 10 | Observability & security | Complete — see [`docs/phases/PHASE_10_COMPLETION.md`](docs/phases/PHASE_10_COMPLETION.md) |
| 11 | Productionization & demo | Complete — see [`docs/phases/PHASE_11_COMPLETION.md`](docs/phases/PHASE_11_COMPLETION.md) |

## Quick start (Phase 11 demo)

```bash
make demo
# open http://127.0.0.1:9101 — paste the printed viewer token
PRISM_E2E=1 pytest -q tests/e2e -m e2e   # optional golden-path proof
```

Talk track: [docs/DEMO_SCRIPT.md](docs/DEMO_SCRIPT.md). No cloud credentials ([ADR-001](docs/adr/001-cost-safety-policy.md)).

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
├── docs/phases/                # PHASE_00…11_COMPLETION.md
├── docker-compose.yml
├── Makefile
├── LICENSE                     # Apache-2.0
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
2. **ADRs** for real decisions — [ADR-001 cost safety](docs/adr/001-cost-safety-policy.md), [ADR-002 multi-warehouse](docs/adr/002-multi-warehouse-activation.md), [ADR-003 Azure DR tradeoff](docs/adr/003-azure-dr-two-cloud-tradeoff.md), [ADR-004 copilot non-fabrication](docs/adr/004-copilot-non-fabrication.md) ([index](docs/adr/index.md)).
3. **Cost safety** — CI never applies Terraform, never calls paid APIs, never runs GPU inference. Emulators only (DuckDB, LocalStack, moto).
4. **Phase discipline** — one phase at a time; each ends with `docs/phases/PHASE_NN_COMPLETION.md`.
5. **Local-first** — `docker compose up` works without cloud credentials.

## Docs

- [ARCHITECTURE.md](ARCHITECTURE.md)
- [ADRs](docs/adr/index.md) (001–004)
- [Demo script](docs/DEMO_SCRIPT.md) (Phase 11)
- [Runbooks](docs/runbooks/README.md) · [Security reviews](docs/security/iam-least-privilege-audit.md)
- [Phase completions](docs/phases/README.md) (00–11)
- [Release plan](docs/RELEASE_PLAN.md) · [Packaging plan](docs/PACKAGING_PLAN.md) · [Changelog](CHANGELOG.md)
- [LICENSE](LICENSE) (Apache-2.0)
