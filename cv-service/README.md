# cv-service

OpenCV preprocessing + ONNX Runtime YOLO-family defect detection (CPU).

| | |
|---|---|
| **Port (host)** | `9102` |
| **Health** | `GET /health` |
| **Detect** | `POST /v1/detect` (multipart) · `POST /v1/detect/path` |
| **Review queue** | `GET /v1/review-queue` → `.data/cv-review-queue/pending/` |
| **Contract** | `contracts/cv-finding-schema` (`CvFinding`) |
| **Labels** | [`docs/LABELS.md`](docs/LABELS.md) |

## Behavior

1. Preprocess with OpenCV: resize → bilateral denoise → CLAHE contrast normalize.
2. Run tiny YOLO-family ONNX on **CPUExecutionProvider** only (ADR-001).
3. Emit schema-valid `CvFinding` records.
4. If `confidence < PRISM_CV_CONFIDENCE_THRESHOLD` → **human-review queue** (not auto-published).
5. Otherwise publish under `.data/cv-findings/published/`.

Tests assert structural correctness only — **no accuracy / mAP claims**.

## Run

```bash
pip install -e contracts/cv-finding-schema -e cv-service
python -m prism_cv_service
curl -s http://localhost:9102/health
curl -s -F asset_id=PRISM-AST-001 -F frame_ref=frm_abcdef123456 \
  -F file=@cv-service/fixtures/images/dent_sample.png \
  http://localhost:9102/v1/detect
```

Docker / Compose:

```bash
docker compose up -d --build cv-service
curl -s http://localhost:9102/health
```

## Environment

| Variable | Default | Meaning |
|----------|---------|---------|
| `PRISM_CV_SERVICE_PORT` | `9102` | HTTP port |
| `PRISM_CV_CONFIDENCE_THRESHOLD` | `0.55` | Below → review queue |
| `PRISM_CV_MODEL_PATH` | `cv-service/models/yolo_fleet_defects_tiny.onnx` | ONNX weights |
| `PRISM_DATA_ROOT` | `.data` | Review + published dirs |
