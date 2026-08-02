# Phase 1 completion — Ingestion & contracts

**Date:** 2026-08-01  
**Status:** Complete (awaiting human go-ahead before Phase 2)

## What shipped

### Contracts

- `contracts/telemetry-schema/` — `SensorPing` + `CameraFrameMetadata` (Pydantic v2) with hydra-style discipline (regex IDs, typed ranges, required timezone-aware UTC timestamps). Committed JSON Schema under `schemas/`.
- `contracts/cv-finding-schema/` — `CvFinding` with defect class enum, confidence bounds, bounding box, segmentation mask ref, `reviewed` flag. Committed JSON Schema under `schemas/`.

### Ingestion

- `ingestion/` mock fleet simulator emitting sensor pings + camera frame refs at configurable rate with configurable corruption injection (hydra `generator.py` pattern).
- Stream producer with **file** fallback (default) and optional **LocalStack** Kinesis backend (`PRISM_INGEST_BACKEND=localstack`). Refuses `amazonaws.com` endpoints (ADR-001).
- Validated records land in an S3-shaped local bronze zone, Hive-partitioned by `dt=` / `device=`. Rejects → `_dlq/`.
- Health server on host port **9105** (`GET /health`).
- Docker Compose service `ingestion` (zero AWS credentials). Optional `localstack` profile.

### Tests & docs

- Unit tests: schema happy-path + rejection paths; simulator/producer/bronze/pipeline.
- `PHASE_1_COMPLETION.md`, updated root README / ARCHITECTURE / component READMEs / CI install steps.

## Deferred (intentionally)

| Item | Lands in |
|------|----------|
| Real camera bytes / image fixtures | Phase 3 |
| Lakehouse bronze→silver→gold | Phase 2 |
| CV service emitting `CvFinding` | Phase 3 |
| Activation / warehouses | Phase 4 |
| Live AWS Kinesis (non-LocalStack) | Phase 6 (manual apply) |

## How to verify

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install pytest ruff pydantic
pip install -e contracts/telemetry-schema -e contracts/cv-finding-schema -e ingestion
make phase1-check
python -m prism_ingestion --duration 3 --rate 10 --failure-rate 0.2 --no-health
find .data/bronze -type f | head
# with Docker daemon running:
make up
curl -s http://localhost:9105/health
```

Local verify for this completion: `make phase1-check` green (35 tests), short file-backend ingest wrote Hive bronze + NDJSON stream. `docker compose config` validates; image build needs a running Docker daemon.

## Stop

Phase 1 only. Do not start Phase 2 until explicitly requested.
