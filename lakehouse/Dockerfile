# PRISM lakehouse — Spark local medallion (ADR-001: no cloud credentials)
FROM python:3.12-slim-bookworm

RUN apt-get update \
  && apt-get install -y --no-install-recommends openjdk-17-jre-headless \
  && rm -rf /var/lib/apt/lists/* \
  && ln -sfn "$(dirname "$(dirname "$(readlink -f "$(which java)")")")" /opt/java

ENV JAVA_HOME=/opt/java \
    PATH="/opt/java/bin:${PATH}" \
    PYTHONUNBUFFERED=1

WORKDIR /app
COPY lakehouse /app/lakehouse
RUN pip install --no-cache-dir /app/lakehouse

ENV PRISM_BRONZE_ROOT=/data/bronze \
    PRISM_WAREHOUSE_ROOT=/data/lakehouse

VOLUME ["/data"]
CMD ["python", "-m", "prism_lakehouse", "--bronze-root", "/data/bronze", "--warehouse-root", "/data/lakehouse"]
