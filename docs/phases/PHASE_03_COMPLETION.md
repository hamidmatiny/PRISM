# Phase 3 completion — Computer vision service

**Date:** 2026-08-01  
**Status:** Complete (awaiting human go-ahead before Phase 4)

## What shipped

- `cv-service/` containerized inference service on host port **9102**.
- OpenCV preprocessing: resize → bilateral denoise → CLAHE contrast normalize.
- ONNX Runtime **YOLO-family** tiny detector (`models/yolo_fleet_defects_tiny.onnx`) on **CPUExecutionProvider** only (ADR-001).
- Label set documented in `cv-service/docs/LABELS.md`: `dent`, `crack`, `tire_wear`, `sensor_obstruction`, `anomaly` (matches `contracts/cv-finding-schema`).
- Outputs validated as `CvFinding` (schema-conformant).
- `PRISM_CV_CONFIDENCE_THRESHOLD` (default `0.55`): low-confidence findings → `.data/cv-review-queue/pending/` for Phase 5 control-plane; high-confidence → `.data/cv-findings/published/`.
- Synthetic fixture images under `cv-service/fixtures/` + structural unit tests (no accuracy claims).
- Compose service `cv-service` bind-mounts `./.data:/data`.

## Verified

| Check | Result |
|-------|--------|
| Unit tests (`pytest -q tests/unit` → 48 passed) | Green |
| `make phase3-check` | Green |
| `docker compose up -d --build cv-service` | `Up (healthy)` on `:9102` |
| `GET /health` | `status=ok`, `CPUExecutionProvider`, threshold `0.55` |
| `POST /v1/detect` (dent fixture) | Schema-valid `CvFinding` payloads; published under `.data/cv-findings/published/` |
| Review routing (`PRISM_CV_CONFIDENCE_THRESHOLD=0.99`) | `published_count=0`, findings land in `.data/cv-review-queue/pending/` with `queue=cv-human-review` |

## Explicit non-claims

- The tiny ONNX model is **CPU-dev / structural**. Tests do **not** assert mAP, recall, or real-world defect accuracy (Vulcan-style discipline).

## Deferred

| Item | Lands in |
|------|----------|
| Control-plane review UI / API consuming the queue | Phase 5 |
| Wiring CV findings into lakehouse gold | Phase 3+ follow-ons / Phase 5 |
| Production-grade trained YOLO weights | Manual / future; not required for CI |

## How to verify

```bash
pip install -e contracts/cv-finding-schema -e cv-service
pytest -q tests/unit/test_cv_service.py
docker compose up -d --build cv-service
curl -s http://localhost:9102/health
curl -s -F asset_id=PRISM-AST-001 -F frame_ref=frm_abcdef123456 \
  -F file=@cv-service/fixtures/images/dent_sample.png \
  http://localhost:9102/v1/detect | head
```

## Stop

Phase 3 only. Do not start Phase 4 until explicitly requested.
