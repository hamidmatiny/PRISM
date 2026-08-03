# drift-monitor

Honest-baseline drift detection (Phase 16) — direct math lineage from
sentinel-ray's `drift_detector.py`, gated by Argus's `baseline_ready`
discipline (ADR-005): no statistical test ever runs against a fabricated
reference.

## What it does

Two feature groups, one per real (non-fabricated) signal source PRISM's
pipeline actually produces:

- **`telemetry_numeric`** — the numeric fields of a validated `SensorPing`
  (speed_mph, latitude, longitude, heading_deg, odometer_km,
  fuel_level_pct). A two-sample KS test runs independently on each feature,
  baseline vs. current rolling window.
- **`cv_geometry`** — a real, low-dimensional feature vector computed from a
  genuine cv-service `CvFinding` (confidence, box width/height, aspect
  ratio, one-hot defect class). PRISM's cv-service is a bounding-box YOLO
  decoder with no embedding head — there is no deep embedding anywhere in
  this codebase, so this is honestly labeled a "feature vector", never an
  "embedding" (see `detector.py`'s module docstring for the full reasoning).
  Centroid distance + KS-on-vector-norms run against this.

## The baseline gate

Per `(asset_id, group)`: only `synthetic_scenario=false` observations count
toward the real baseline. Once `PRISM_DRIFT_BASELINE_SAMPLES` (default 20)
real samples exist, the baseline freezes permanently and detection goes
live. Before that, `/health` reports `baseline_ready: false` for that
tracker and a structural-only `cold_start_synthetic_placeholder` is shown —
fabricated, standard-normal values, **never** passed into `ks_2samp`,
`centroid_distance`, or `ks_on_norms`. See `baseline.py`.

Once live, *every* subsequent observation — synthetic or real — feeds the
comparison window (checking whether *current* traffic, including
scenario-engine's reproducible `drift_signature` chaos outcome, has drifted
away from the earned baseline is exactly the point).

## Wiring to incident-engine

A detection run that finds `drifted_feature_count >= 1` fire-and-forgets
`POST /v1/observations {"kind": "drift", "detail": {"drifted_feature_count": N, ...}}`
to incident-engine — exactly the `record_drift()` hook Phase 14 shipped
dormant-but-wired, waiting for this producer. incident-engine's own
`drifted_features_threshold` policy (default 2) decides whether that trips
the asset's breaker; drift-monitor only reports the observed count, it
never decides the trip itself.

## API

- `GET /health` — service status + `baseline_ready` + full per-asset,
  per-group status.
- `GET /v1/status` — same status payload without the service metadata.
- `POST /v1/observe` — `{"asset_id", "group": "telemetry_numeric"|"cv_geometry", "payload", "synthetic_scenario"}`.
  Fed by `ingestion` (telemetry) and `cv-service` (CV findings); see their
  `drift_client.py`.

## Local run

```bash
cd drift-monitor
pip install -e .
PRISM_DRIFT_BASELINE_SAMPLES=5 PRISM_DRIFT_WINDOW_SIZE=5 python -m prism_drift_monitor
curl http://127.0.0.1:9109/health
```
