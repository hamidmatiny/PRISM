# Phase 10 load test results

**When:** 2026-08-02T05:01:54Z (local compose)  
**Command:**

```bash
TOKEN=$(docker compose exec -T control-plane python manage.py print_api_token viewer)
python observability/load-tests/run_load_test.py --token "$TOKEN" --concurrency 8 --requests 40
```

**Raw JSON:** `observability/load-tests/last-run.json`

## Summary

| Endpoint | n | err% | p50 ms | p95 ms | mean ms |
|----------|---|------|--------|--------|---------|
| activation.health | 40 | 0.0 | 27.0 | 46.5 | 28.5 |
| activation.query | 40 | 0.0 | 21.0 | 32.3 | 22.5 |
| control_plane.health | 40 | 0.0 | 1.9 | 3.7 | 2.2 |
| control_plane.me | 40 | 0.0 | 7.9 | 12.0 | 8.4 |
| control_plane.work_orders | 40 | 0.0 | 8.1 | 11.3 | 8.3 |
| cockpit.proxy.control_health | 40 | 0.0 | 5.1 | 14.1 | 7.1 |

- Wall clock: **0.39 s** for 240 requests at concurrency 8
- All endpoints **0% errors** (HTTP 200)
- Cockpit surface exercised via Vite proxy `:9101/proxy/control/health`
- Activation query path used live fixture gold after `/v1/activate`

## Notes

- Not a capacity certification — basic concurrency probe for Phase 10.
- Host machine was already warm (services healthy; OTel collector running).
