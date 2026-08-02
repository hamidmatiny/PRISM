# Phase 0 completion — Foundation

**Date:** 2026-08-01  
**Status:** Complete (awaiting human review before Phase 1)

## What shipped

- Monorepo scaffold matching the build-brief layout (`contracts/`, service dirs, `lakehouse/`, `dbt/`, `infra/terraform/{aws,azure}/`, `observability/`, `docs/`, `examples/`, `tests/`).
- [ADR-001](../adr/001-cost-safety-policy.md) — CI never touches real cloud resources, paid APIs, or GPU inference; DuckDB / LocalStack / moto for tests; `terraform apply` is manual only.
- Cursor rules under `.cursor/rules/`:
  - `cost-safety.mdc`
  - `contract-first.mdc`
  - `monorepo.mdc`
  - `phase-completion.mdc`
- CI skeleton [`.github/workflows/ci.yml`](../../.github/workflows/ci.yml): lint (ruff), unit tests (pytest), terraform `validate` + `tflint` + `checkov` for aws/azure stacks.
- Empty-but-valid Terraform scaffolds (`null` provider) under `infra/terraform/aws` and `infra/terraform/azure`.
- Contract stubs: `telemetry-schema`, `cv-finding-schema`, `activation-contract` (minimal OpenAPI health stub).
- Root [`README.md`](../../README.md), [`ARCHITECTURE.md`](../../ARCHITECTURE.md) (mermaid diagram), component `README.md` files, `.env.example`, `Makefile`, `docker-compose.yml` with a Phase 0 foundation stub on port `9199`.
- Foundation unit tests in `tests/unit/test_foundation.py`.

## Deferred (intentionally)

| Item | Lands in |
|------|----------|
| Real telemetry / CV / activation schemas | Phases 1, 3, 4 |
| Mock fleet simulator + Kinesis / LocalStack | Phase 1 |
| Lakehouse transforms, dbt models | Phase 2 |
| CV inference service | Phase 3 |
| Warehouse adapters | Phase 4 |
| Django control plane | Phase 5 |
| Real AWS / Azure Terraform modules | Phases 6 / 7 |
| Cockpit / copilot | Phases 8 / 9 |
| Full observability + e2e golden path | Phases 10 / 11 |

## How to verify

```bash
cp .env.example .env
python3 -m venv .venv && source .venv/bin/activate
pip install pytest ruff
make phase0-check         # lint + unit tests + terraform validate
make up                   # http://localhost:9199
```

Optional (mirrors CI extras if installed locally):

```bash
# tflint / checkov — installed in GitHub Actions; optional locally
cd infra/terraform/aws && tflint --init && tflint
```

## Suggested commit message

```text
phase-0: scaffold monorepo, ADR-001, cursor rules, and CI skeleton
```

Commit not created automatically — say if you want it committed.

## Stop

Phase 0 only. Do not start Phase 1 until explicitly requested.
