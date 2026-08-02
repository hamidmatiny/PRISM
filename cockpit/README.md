# cockpit

Vue 3 + Vite + Pinia digital-twin UI for PRISM fleet ops.

| | |
|---|---|
| **Port (host)** | `9101` |
| **3D** | Three.js `WebGPURenderer` with automatic WebGL backend fallback |
| **Shaders** | TSL node materials (no hand-written GLSL/WGSL) |
| **Backends** | control-plane `:9100`, activation-gateway `:9103`, ai-copilot `:9104` (Ask PRISM) |

Dark theme is the default — fleet-ops tooling is typically used in low-light
control rooms (UX, not decoration). Tokens live in `src/styles/tokens.css`.

## What you should see

1. A dark shell branded **PRISM** with a 3D floor of fleet assets.
2. Asset color/glow driven by **open work orders + unreviewed CV findings** from
   control-plane (not a flat legend).
3. Click an asset → detail panel with:
   - telemetry bars from activation-gateway `POST /v1/query`
   - CV frame + bounding box from control-plane finding + fixture frame
   - work-order history from control-plane
4. **Ask PRISM** panel (`:9104`) — tool-grounded answers only ([ADR-004](../docs/adr/004-copilot-non-fabrication.md)).
5. Bottom **incident scrubber** replaying CV → work order → telemetry events.

Demo path: `make demo` from repo root (seeded gold + screenshots under `docs/screenshots/`).

## Test it yourself

Backends must already be up (same continuity as every prior phase):

```bash
# From repo root
docker compose up -d --build control-plane control-plane-worker activation-gateway cv-service

# Bare token only (do NOT use manage.py shell — it prints import banners)
TOKEN=$(docker compose exec -T control-plane python manage.py print_api_token viewer)
echo "$TOKEN"   # expect a single 48-char hex line

# Prove auth before opening the UI (must be HTTP 200 + JSON list)
curl -sS -w "\nHTTP:%{http_code}\n" \
  -H "Authorization: Bearer $TOKEN" \
  http://127.0.0.1:9100/api/v1/work-orders

cd cockpit
npm install
npm run dev
# open http://localhost:9101
# paste $TOKEN into "API token", click Use token
# expect: header shows "auth: viewer", HUD "N assets", scrubber "N events"
```

With the Vite proxy up, also run the same-path smoke the browser uses:

```bash
# second terminal, repo root, while npm run dev is listening on :9101
TOKEN=$(docker compose exec -T control-plane python manage.py print_api_token viewer) \
  node cockpit/scripts/smoke-auth.mjs
```

Or via compose (Vite in container, still open the host browser):

```bash
docker compose up -d --build cockpit
open http://localhost:9101
```

Structural / CI checks (no GPU, no cloud):

```bash
cd cockpit && npm ci && npm run typecheck && npm run build
node --test src/lib/token.test.mjs
make phase8-check   # from repo root: lint + unit tests + cockpit-build
```

## Design system

- Color tokens, spacing scale, typography: `src/styles/tokens.css`
- Focus rings, `prefers-reduced-motion`, contrast-oriented health hues: `src/styles/base.css`
- Keyboard: Esc closes detail panel; canvas is focusable; scrubber range is keyboard-operable
