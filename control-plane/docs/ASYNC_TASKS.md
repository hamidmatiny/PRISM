# Why Django-Q2 for gold writeback

Approved / relabeled findings must land in the gold findings zone
(`reviewed=true`) without blocking the review API. Options considered:

| Option | Pros | Cons |
|--------|------|------|
| **Django-Q2 (chosen)** | ORM broker works with SQLite local + Postgres RDS; no Redis required for `docker compose up`; same process model as Django; easy `Q_CLUSTER['sync']=True` in tests | Smaller ecosystem than Celery |
| Celery + Redis/RabbitMQ | Industry default at scale | Extra broker service for local/CI; conflicts with ADR-001 zero-creds local path |
| Inline write in request | Simplest | Couples API latency to disk I/O; no retry |

**Decision:** Django-Q2 with `orm: default` broker. Local SQLite and RDS Postgres
both work. Compose runs `control-plane-worker` (`manage.py qcluster`) beside the
API for Postgres. On SQLite (local fallback) writeback runs **inline in the
request** to avoid multi-process SQLite locks; tests set `PRISM_Q_SYNC=1` for the
same reason.
