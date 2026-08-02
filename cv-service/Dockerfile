# PRISM CV service — OpenCV + ONNX Runtime CPU (ADR-001: no GPU)
FROM python:3.12-slim-bookworm

RUN apt-get update \
  && apt-get install -y --no-install-recommends libgl1 libglib2.0-0 \
  && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY contracts/cv-finding-schema /app/contracts/cv-finding-schema
COPY observability/otel /app/observability/otel
COPY cv-service /app/cv-service

RUN pip install --no-cache-dir \
      /app/contracts/cv-finding-schema \
      /app/observability/otel \
      /app/cv-service

ENV PRISM_CV_SERVICE_PORT=9102 \
    PRISM_DATA_ROOT=/data \
    PRISM_CV_MODEL_PATH=/app/cv-service/models/yolo_fleet_defects_tiny.onnx \
    PRISM_CV_LABELS_PATH=/app/cv-service/models/labels.json \
    PRISM_CV_CONFIDENCE_THRESHOLD=0.55 \
    PYTHONUNBUFFERED=1

EXPOSE 9102
VOLUME ["/data"]

HEALTHCHECK --interval=10s --timeout=3s --retries=5 --start-period=20s \
  CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:9102/health')"

CMD ["python", "-m", "prism_cv_service"]
