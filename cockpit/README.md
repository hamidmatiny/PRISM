# cockpit

Vue 3 + Vite + Pinia digital-twin UI for PRISM fleet ops.

| | |
|---|---|
| **Port (host)** | `9101` |
| **3D** | Three.js `WebGPURenderer` with automatic WebGL backend fallback |
| **Shaders** | TSL node materials (no hand-written GLSL/WGSL) |
| **Backends** | control-plane `:9100`, activation-gateway `:9103` (real API shapes) |

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
4. Bottom **incident scrubber** replaying CV → work order → telemetry events.

## Test it yourself

Backends must already be up (same continuity as every prior phase):

```bash
# From repo root
docker compose up -d --build control-plane control-plane-worker activation-gateway cv-service

# Bearer token from control-plane bootstrap
TOKEN=$(docker compose exec -T -e DJANGO_SETTINGS_MODULE=prism_control.settings \
  control-plane python -c \
  "import django; django.setup(); from fleet.models import UserProfile; \
   print(UserProfile.objects.get(user__username='viewer').api_token)")
echo "$TOKEN"

cd cockpit
npm install
npm run dev
# open http://localhost:9101
# paste $TOKEN into "API token", click Use token → Refresh fleet
```

Or via compose (Vite in container, still open the host browser):

```bash
docker compose up -d --build cockpit
open http://localhost:9101
```

Structural / CI checks (no GPU, no cloud):

```bash
cd cockpit && npm ci && npm run typecheck && npm run build
make phase8-check   # from repo root: lint + unit tests + cockpit-build
```

## Design system

- Color tokens, spacing scale, typography: `src/styles/tokens.css`
- Focus rings, `prefers-reduced-motion`, contrast-oriented health hues: `src/styles/base.css`
- Keyboard: Esc closes detail panel; canvas is focusable; scrubber range is keyboard-operable
