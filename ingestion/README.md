# ingestion

Mock fleet simulator + Kinesis producer (file / LocalStack) + S3-shaped bronze landing.

| | |
|---|---|
| **Port (host)** | `9105` |
| **Health** | `GET /health` → JSON status + counters |
| **Standalone** | `python -m prism_ingestion` (after installing contracts + this package) |

## What it does

1. Emits **sensor pings** and **camera frame metadata** at `PRISM_EMIT_RATE` (Hz).
2. Injects corrupt payloads at `PRISM_FAILURE_RATE` (hydra-style resilience testing).
3. Validates against `contracts/telemetry-schema` — rejects go to bronze `_dlq/`.
4. Publishes accepted events to a stream backend:
   - `file` (default) — Kinesis-shaped NDJSON under `$PRISM_DATA_ROOT/kinesis/...`
   - `localstack` — `put_record` against LocalStack (never real AWS; ADR-001)
5. Lands accepted records in a Hive-partitioned bronze zone:
   `$PRISM_DATA_ROOT/bronze/{sensor_pings|camera_frames}/dt=YYYY-MM-DD/device=PRISM-DEV-NNN/*.json`

## Run locally

```bash
# from repo root
python3 -m venv .venv && source .venv/bin/activate
pip install -e contracts/telemetry-schema -e ingestion
python -m prism_ingestion --duration 5 --rate 5 --failure-rate 0.1 --no-health
```

Or via Compose (zero cloud credentials):

```bash
make up
curl -s http://localhost:9105/health | jq .
```

Optional LocalStack:

```bash
PRISM_INGEST_BACKEND=localstack docker compose --profile localstack up -d
```

## Environment

| Variable | Default | Meaning |
|----------|---------|---------|
| `PRISM_INGEST_BACKEND` | `file` | `file` or `localstack` |
| `PRISM_DATA_ROOT` | `.data` | Bronze + file-stream root |
| `PRISM_EMIT_RATE` | `2` | Events per second |
| `PRISM_FAILURE_RATE` | `0.05` | Corruption probability |
| `PRISM_DURATION_SECONDS` | `0` | `0` = run until stopped |
| `PRISM_ASSET_IDS` | `PRISM-AST-001,002,003` | Comma-separated assets |
| `PRISM_INGESTION_PORT` | `9105` | Health HTTP port |
| `LOCALSTACK_ENDPOINT` | `http://localhost:4566` | Used when backend=`localstack` |
