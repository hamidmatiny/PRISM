# control-plane

Django 5.x + Django Ninja control plane: assets, work orders, CV human-review, RBAC, audit.

| | |
|---|---|
| **Port (host)** | `9100` |
| **Health** | `GET /health` |
| **Admin** | `http://localhost:9100/admin/` |
| **API** | `http://localhost:9100/api/v1/…` (Bearer token) |
| **DB** | `DATABASE_URL` (Postgres); SQLite fallback under `.data/control-plane/` |
| **Queue input** | `.data/cv-review-queue/pending/` (written by `cv-service`) |
| **Gold writeback** | `.data/lakehouse/gold/cv_findings/<finding_id>.json` (`reviewed=true`) |

## Roles

| Role | Capabilities |
|------|----------------|
| `viewer` | Read assets, findings, review queue |
| `inspector` | Sync queue, approve/reject/relabel, create work orders, read audit |
| `fleet-admin` | All of the above + create assets |

Bootstrap users (password `PRISM_BOOTSTRAP_PASSWORD`, default `prism-local-dev`):
`viewer`, `inspector`, `fleetadmin`, `admin` (superuser). Tokens printed by
`python manage.py bootstrap_rbac`.

## Async gold writeback

Django-Q2 with ORM broker — see [docs/ASYNC_TASKS.md](docs/ASYNC_TASKS.md).
SQLite local runs writeback inline; Postgres uses `control-plane-worker` (`qcluster`).

## Quick start

```bash
pip install -e contracts/cv-finding-schema -e control-plane
docker compose up -d --build control-plane control-plane-worker
curl -s http://localhost:9100/health

# Bare token (print_api_token — not manage.py shell, which adds import banners):
TOKEN=$(docker compose exec -T control-plane python manage.py print_api_token inspector)
curl -s http://localhost:9100/api/v1/review-queue -H "Authorization: Bearer $TOKEN"
```

## Review workflow

1. `cv-service` writes low-confidence findings to `cv-review-queue/pending/`.
2. Inspector lists/syncs via API or Django admin.
3. `POST /api/v1/review-queue/{finding_id}/decide` with `approve` | `reject` | `relabel`.
4. Pending file moves to `cv-review-queue/decided/`; approve/relabel enqueue gold writeback.
5. Every state change appends an `AuditLogEntry`.
