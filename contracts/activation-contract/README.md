# activation-contract

Warehouse-agnostic **activate + query** OpenAPI contract — PRISM's namesake surface.

> One gold table, split into many warehouses — like a prism splitting light.

## Status

**Phase 4** — OpenAPI `1.0.0` + Pydantic models (`prism-activation-contract`).

## Operations

| Operation | Path | Purpose |
|-----------|------|---------|
| Activate | `POST /v1/activate` | Activate gold table X into warehouse Y |
| Query | `POST /v1/query` | Query table X regardless of which warehouse serves it (`warehouse=auto`) |
| Routing | `GET /v1/routing/{table}` | Inspect current warehouse routing |
| Warehouses | `GET /v1/warehouses` | Adapter catalog |
| Health | `GET /health` | Liveness |

Canonical source: [`openapi.yaml`](./openapi.yaml) (also packaged under `prism_activation_contract`).

## Consumers

- `activation-gateway/` (implementer)
- `control-plane/`, `cockpit/`, `ai-copilot/` (clients in later phases)

## Install

```bash
pip install -e contracts/activation-contract
```
