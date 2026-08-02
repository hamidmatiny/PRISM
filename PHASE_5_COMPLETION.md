# Phase 5 completion — Control plane

**Date:** 2026-08-01  
**Status:** Complete (awaiting human go-ahead before Phase 6)

## What shipped

- Django 5.x + Django Ninja control plane on host port **9100**.
- Models: `Asset`, `WorkOrder`, `InspectionFinding`, `ReviewDecision`, `AuditLogEntry` (+ `UserProfile` for API tokens).
- Human-review workflow reads **actual** `cv-review-queue/pending/*.json` files written by `cv-service` (same envelope shape / `ReviewQueue` writer — not a hand-rolled fixture of the queue).
- Inspector/fleet-admin approve / reject / relabel via Ninja API and Django admin actions.
- Approved/relabeled findings → **lakehouse gold** (`.data/lakehouse/gold/cv_findings/<id>.json`) with `reviewed=true`, schema-validated via `cv-finding-schema`.
- Async path: **Django-Q2** ORM broker (see `control-plane/docs/ASYNC_TASKS.md`); SQLite local writeback is inline.
- RBAC: `viewer`, `inspector`, `fleet-admin` enforced at the API layer.
- Postgres via `PRISM_DATABASE_URL`; SQLite fallback under `.data/control-plane/`.
- Full audit trail on sync, decisions, asset/work-order creates.

## Verified

| Check | Result |
|-------|--------|
| `make phase5-check` | **60 passed** |
| `docker compose up -d --build control-plane control-plane-worker` | `control-plane` **Up (healthy)** on `:9100`; SQLite at `/data/control-plane/db.sqlite3` |
| `GET /health` | `{"status": "ok", "service": "control-plane"}` |
| `GET /api/v1/review-queue` | Listed real pending `fnd_*` from bind-mounted `.data/cv-review-queue/pending/` |
| Approve `fnd_151e555be235` gold writeback | File at `.data/lakehouse/gold/cv_findings/fnd_151e555be235.json` with `"reviewed": true` |

## Explicit non-claims

- SQLite local is a **dev fallback**, not the production RDS shape.
- Gold writeback is schema-valid `CvFinding` JSON under the lakehouse gold root (`lakehouse/gold/cv_findings/`), alongside Spark parquet gold tables — not a rewrite of `asset_daily_metrics` parquet.

## Deferred

| Item | Lands in |
|------|----------|
| Cockpit UI over control-plane APIs | Phase 8 |
| Real RDS Multi-AZ Terraform wiring | Phase 6 |
| Copilot tools over work orders / review | Phase 9 |

## How to verify

```bash
pip install -e contracts/cv-finding-schema -e control-plane
pytest -q tests/unit/test_control_plane.py
docker compose up -d --build control-plane control-plane-worker
curl -s http://localhost:9100/health
TOKEN=$(docker compose exec -T control-plane python -c \
  "import django; django.setup(); from fleet.models import UserProfile; \
   print(UserProfile.objects.get(user__username='inspector').api_token)")
curl -s http://localhost:9100/api/v1/review-queue -H "Authorization: Bearer $TOKEN" | head
```

## Stop

Phase 5 only. Do not start Phase 6 until explicitly requested.
