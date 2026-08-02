# Phase 8 completion — Digital twin cockpit

**Date:** 2026-08-02  
**Status:** Complete (awaiting human go-ahead before Phase 9)

## What shipped

- Vite + Vue 3 + Pinia app under `cockpit/` on host port **9101**
- Design system first: tokens (color / spacing / type), **dark default** for
  control-room use, focus rings, reduced-motion, keyboard Esc to close panel
- Three.js **WebGPURenderer** with automatic WebGL backend fallback; health
  materials via **TSL** (no hand-written GLSL/WGSL)
- Fleet assets colored/glowed from **open work orders + unreviewed CV findings**
  (control-plane), not a flat status legend
- Detail panel wired to real backends:
  - telemetry → activation-gateway `POST /v1/query` (`asset_daily_metrics`)
  - CV frame + bbox → control-plane finding + `/api/v1/frames/{frame_ref}`
  - work orders → `GET /api/v1/work-orders?asset_id=`
- **Incident scrubber** replaying CV findings → work orders → telemetry markers
- Continuity helpers on backends: CORS, `bounding_box` / `created_at` on APIs,
  frame fixture serving for cockpit overlays
- Compose service `cockpit`; README **Test it yourself** section

## Verified

| Check | Result |
|-------|--------|
| `cd cockpit && npm ci && npm run typecheck && npm run build` | Green locally; CI job `cockpit` |
| `make test` (65 unit tests) | Green |
| Live `:9100` review-queue includes `bounding_box` + `detected_at` | Green |
| Live `:9100` `/api/v1/frames/{frame_ref}` serves fixture PNG | Green |
| Live `:9103` activate + query `asset_daily_metrics` | Green |
| GitHub Actions run for this commit | Linked after push |

## Explicit non-claims

- Frame bytes use **cv-service fixtures** keyed by finding `defect_class` when
  live camera files are not retained on disk — `frame_ref` + class still come
  from real finding payloads.
- WebGPU availability depends on the browser; HUD shows active backend.

## Stop

Phase 8 only. Do not start Phase 9 until explicitly requested.
