# Phase 5 completion — Control plane

**Date:** 2026-08-01  
**Status:** Complete (awaiting human go-ahead before Phase 6)

## What shipped

- Django 5.x + Django Ninja control plane on host port **9100**.
- Models: `Asset`, `WorkOrder`, `InspectionFinding`, `ReviewDecision`, `AuditLogEntry` (+ `UserProfile` for API tokens).
- Human-review workflow reads **actual** `cv-review-queue/pending/*.json` files written by `cv-service` (same envelope shape / `ReviewQueue` writer — not a hand-rolled fixture of the queue).
- Inspector/fleet-admin approve / reject / relabel via Ninja API and Django admin actions.
- Approved/relabeled findings → gold findings zone (`.data/cv-findings/gold/`) with `reviewed=true`, schema-validated via `cv-finding-schema`.
- Async path: **Django-Q2** ORM broker (see `control-plane/docs/ASYNC_TASKS.md`); SQLite local writeback is inline.
- RBAC: `viewer`, `inspector`, `fleet-admin` enforced at the API layer.
- `DATABASE_URL` Postgres; SQLite fallback under `.data/control-plane/`.
- Full audit trail on sync, decisions, asset/work-order creates.

## Verified

| Check | Result |
|-------|--------|
| Unit tests (`test_control_plane.py`) | Green — includes live pending-dir read when `.data/cv-review-queue/pending/` is populated |
| `docker compose up -d --build control-plane control-plane-worker` | Healthy on `:9100` |
| `GET /health` | `status=ok` |
| `GET /api/v1/review-queue` with inspector token | Listed **20** real pending `fnd_*` envelopes from bind-mounted `.data` (e.g. `fnd_151e555be235`) |
| Approve live `fnd_151e555be235` | → `decided/` + `.data/cv-findings/gold/…` with `reviewed=true` + audit `review_decision.approve` |

## Explicit non-claims

- SQLite local is a **dev fallback**, not the production RDS shape.
- Gold writeback for CV findings is the `cv-findings/gold` zone (schema-valid `CvFinding`); lakehouse Spark gold tables for findings remain a later wiring step.

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
