# Contracts

Single source of truth for cross-service schemas. Services **import** from here — they never duplicate field lists.

| Contract | Path | Status | Consumers |
|----------|------|--------|-----------|
| Telemetry | `telemetry-schema/` | **Phase 1** — Pydantic + JSON Schema | ingestion, lakehouse, cv-service |
| CV finding | `cv-finding-schema/` | **Phase 1** — Pydantic + JSON Schema | cv-service, control-plane, lakehouse, ai-copilot |
| Activation | `activation-contract/` | Stub until Phase 4 | activation-gateway, control-plane, cockpit, ai-copilot |

See `.cursor/rules/contract-first.mdc`.
