# Contracts

Single source of truth for cross-service schemas. Services **import** from here — they never duplicate field lists.

| Contract | Path | Filled in | Consumers |
|----------|------|-----------|-----------|
| Telemetry | `telemetry-schema/` | Phase 1 | ingestion, lakehouse, cv-service |
| CV finding | `cv-finding-schema/` | Phase 1 / 3 | cv-service, control-plane, lakehouse, ai-copilot |
| Activation | `activation-contract/` | Phase 4 | activation-gateway, control-plane, cockpit, ai-copilot |

Phase 0 ships directory stubs + package markers only. See `.cursor/rules/contract-first.mdc`.
