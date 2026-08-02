# PRISM ai-copilot — tool-grounded Ask PRISM (ADR-001: no paid LLM in default path)
FROM python:3.12-slim-bookworm

WORKDIR /app
COPY ai-copilot /app/ai-copilot

RUN pip install --no-cache-dir /app/ai-copilot

ENV PRISM_AI_COPILOT_PORT=9104 \
    PRISM_ACTIVATION_URL=http://activation-gateway:9103 \
    PRISM_CONTROL_PLANE_URL=http://control-plane:9100 \
    PRISM_DATA_ROOT=/data \
    PRISM_CV_FINDINGS_GOLD_DIR=/data/lakehouse/gold/cv_findings \
    PRISM_CORS_ORIGINS=http://localhost:9101,http://127.0.0.1:9101 \
    PYTHONUNBUFFERED=1

EXPOSE 9104
VOLUME ["/data"]

HEALTHCHECK --interval=10s --timeout=3s --retries=5 --start-period=20s \
  CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:9104/health')"

CMD ["python", "-m", "prism_ai_copilot"]
