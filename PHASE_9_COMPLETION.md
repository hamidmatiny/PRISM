# Phase 9 completion — AI copilot (Ask PRISM)

**Date:** 2026-08-02  
**Status:** Complete (awaiting human go-ahead before Phase 10)

## What shipped

- `ai-copilot/` FastAPI service on **:9104** with `GET /health` and `POST /v1/ask`
- Tools wired to **real** backends:
  - activation-gateway warehouse query contract
  - control-plane CV review-queue + findings + gold writeback dir
  - control-plane work orders
- [ADR-004](docs/adr/004-copilot-non-fabrication.md) non-fabrication contract
- Structural grounding tests (Vulcan ADR-014 pattern): parse answer → every
  cited number/id must appear in that turn’s tool evidence
- Light-touch prompt-injection + PII validation (not a full aegis policy engine)
- Cockpit **Ask PRISM** panel + Vite proxy `/proxy/copilot`
- Compose service `ai-copilot`; README **Test it yourself**

## Verified

| Check | Result |
|-------|--------|
| Unit grounding + validation tests | Green |
| Warehouse ask against live activation-gateway (in-process mocks) | Green |
| CV + WO ask against Django live_server + bootstrap token | Green |
| `cd cockpit && npm run typecheck && npm run build` | Green |
| GitHub Actions for this commit | Linked after push |

## Explicit non-claims

- Default synthesis is template-based — no paid LLM quality claims.
- Copilot does not mutate fleet state (read-only tools).

## Stop

Phase 9 only. Do not start Phase 10 until explicitly requested.
