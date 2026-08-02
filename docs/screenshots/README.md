# Cockpit screenshots (Phase 11)

Captured from a live local stack (`make demo`) on 2026-08-02T05:17:24.781Z.

| File | View |
|------|------|
| `cockpit-fleet-twin.png` | Digital twin fleet floor |
| `cockpit-asset-detail.png` | After canvas interaction / detail context |
| `cockpit-ask-prism.png` | Ask PRISM panel |

Re-capture:

```bash
make demo
cd cockpit && npm install -D playwright && npx playwright install chromium
VIEWER_TOKEN=$(docker compose exec -T control-plane python manage.py print_api_token viewer | tail -n1) \
  node scripts/capture-demo-screenshots.mjs
```
