# ADR 004 — Ask PRISM copilot non-fabrication contract

**Status:** Accepted  
**Date:** 2026-08  
**Phases:** 9 (`ai-copilot/`)

## Context

Phase 9 adds a natural-language “Ask PRISM” surface in the cockpit. The failure
mode is a chatbot that wraps a paid LLM and invents warehouse metrics, CV
counts, or work-order statuses. That would break PRISM’s continuity bar — the
same discipline that already caught real gaps when cockpit/auth and lakehouse
paths were only proven structurally.

This ADR follows the same proof pattern as Vulcan
[ADR-014](https://github.com/hamidmatiny/Vulcan/blob/main/docs/adr/014-langgraph-advisor-non-fabrication-scope.md):
tool-grounded answers with CI that asserts numbers/ids appear in that turn’s
tool evidence.

## Decision

1. **Tool-grounded only.** `ai-copilot/` answers only after calling real tools
   against live (or locally composed) backends:
   - `query_warehouse` → activation-gateway `POST /v1/query` (activation contract)
   - `query_cv_findings` → control-plane review-queue + findings, plus gold
     writeback dir `.data/lakehouse/gold/cv_findings/`
   - `query_work_orders` → control-plane `GET /api/v1/work-orders`
2. **Non-fabrication rule.** Every numeric value and claimable identifier in
   the final `answer` string **must** appear in the evidence bag collected from
   tool calls (or the user question) in that same turn. If a claim cannot be
   grounded, the copilot says so instead of guessing.
3. **No paid LLM in CI / default path.** Synthesis uses deterministic templates
   filled from tool results (ADR-001). Hosted LLM commentary is out of scope
   for Phase 9.
4. **Light-touch I/O validation only.** Basic prompt-injection rejection and
   obvious PII redaction on outputs. A full policy engine is **aegis** — do not
   duplicate it here.

## Alternatives considered

| Option | Why not |
|--------|---------|
| Chatbot over OpenAI/Anthropic with “context dump” | Easy to hallucinate numbers; paid API; fails ADR-001 |
| Mocked tool JSON in CI only | Greenwashes continuity; same class of gap as Phase 2 fixtures |
| Full aegis policy engine inside ai-copilot | Wrong layer; keep PRISM thin and call aegis later if needed |

## Consequences

- Cockpit “Ask PRISM” panel calls `POST /v1/ask` on `:9104`.
- Unit tests parse answers and assert cited numbers/ids ⊆ tool evidence for
  that run; a fabricated number fails CI.
- Operators get an explainable `tool_calls` + `evidence` trail with every answer.

## Compliance

- CI installs `ai-copilot` and runs grounding tests.
- Never require `OPENAI_API_KEY` / `ANTHROPIC_API_KEY` for green CI.
