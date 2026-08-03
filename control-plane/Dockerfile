# PRISM control-plane — Django 5 + Ninja + Django-Q2 (ADR-001: SQLite local OK)
FROM python:3.12-slim-bookworm

WORKDIR /app
COPY contracts/cv-finding-schema /app/contracts/cv-finding-schema
COPY observability/otel /app/observability/otel
COPY control-plane /app/control-plane

RUN pip install --no-cache-dir \
      /app/contracts/cv-finding-schema \
      /app/observability/otel \
      /app/control-plane \
      gunicorn

WORKDIR /app/control-plane
RUN chmod +x entrypoint.sh

# Bake admin's CSS/JS + our own static assets into a hashed manifest at build
# time (not on every container start) -- served at runtime by WhiteNoiseMiddleware.
# SECRET_KEY has a local-dev default in settings.py so this needs no real secret,
# and collectstatic never touches the database.
ENV DJANGO_SETTINGS_MODULE=prism_control.settings
RUN python manage.py collectstatic --noinput

ENV PRISM_CONTROL_PLANE_PORT=9100 \
    PRISM_DATA_ROOT=/data \
    PRISM_CV_REVIEW_PENDING_DIR=/data/cv-review-queue/pending \
    PRISM_CV_REVIEW_DECIDED_DIR=/data/cv-review-queue/decided \
    PRISM_CV_FINDINGS_GOLD_DIR=/data/lakehouse/gold/cv_findings \
    DJANGO_SETTINGS_MODULE=prism_control.settings \
    DJANGO_DEBUG=0 \
    DJANGO_ALLOWED_HOSTS=localhost,127.0.0.1,0.0.0.0 \
    PYTHONUNBUFFERED=1

EXPOSE 9100
VOLUME ["/data"]

HEALTHCHECK --interval=10s --timeout=3s --retries=5 --start-period=30s \
  CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:9100/health')"

ENTRYPOINT ["./entrypoint.sh"]
CMD ["gunicorn", "prism_control.wsgi:application", "--bind", "0.0.0.0:9100", "--workers", "2"]
