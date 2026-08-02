-- PRISM Unity Catalog bootstrap
-- GENERATED from lakehouse/quality/expectations.yaml — do not hand-edit.
-- Regenerate: python lakehouse/unity_catalog/render_bootstrap.py
-- Apply manually against a real Databricks workspace (ADR-001). Never from CI.

CREATE CATALOG IF NOT EXISTS prism;
USE CATALOG prism;

CREATE SCHEMA IF NOT EXISTS prism.bronze;
CREATE SCHEMA IF NOT EXISTS prism.silver;
CREATE SCHEMA IF NOT EXISTS prism.gold;

CREATE TABLE IF NOT EXISTS prism.silver.sensor_pings (
  asset_id STRING,
  device_id STRING,
  event_ts TIMESTAMP,
  speed_mph DOUBLE,
  latitude DOUBLE,
  longitude DOUBLE,
  heading_deg DOUBLE,
  odometer_km DOUBLE,
  fuel_level_pct DOUBLE,
  schema_version STRING,
  event_date DATE
) USING DELTA;
COMMENT ON TABLE prism.silver.sensor_pings IS 'Typed, deduplicated sensor pings from bronze JSON.';
ALTER TABLE prism.silver.sensor_pings SET TBLPROPERTIES (
  'quality.expectations_source' = 'lakehouse/quality/expectations.yaml',
  'quality.expectation.asset_id_not_null' = 'asset_id IS NOT NULL',
  'quality.expectation.asset_id_not_null.action' = 'fail',
  'quality.expectation.device_id_not_null' = 'device_id IS NOT NULL',
  'quality.expectation.device_id_not_null.action' = 'fail',
  'quality.expectation.timestamp_not_null' = 'event_ts IS NOT NULL',
  'quality.expectation.timestamp_not_null.action' = 'fail',
  'quality.expectation.speed_range' = 'speed_mph BETWEEN 0 AND 120',
  'quality.expectation.speed_range.action' = 'drop',
  'quality.expectation.latitude_range' = 'latitude BETWEEN -90 AND 90',
  'quality.expectation.latitude_range.action' = 'drop',
  'quality.expectation.longitude_range' = 'longitude BETWEEN -180 AND 180',
  'quality.expectation.longitude_range.action' = 'drop',
  'quality.expectation.asset_id_pattern' = 'asset_id RLIKE ''^PRISM-AST-[0-9]{3}$''',
  'quality.expectation.asset_id_pattern.action' = 'drop'
);

CREATE TABLE IF NOT EXISTS prism.silver.camera_frames (
  asset_id STRING,
  device_id STRING,
  frame_id STRING,
  event_ts TIMESTAMP,
  storage_uri STRING,
  content_type STRING,
  width_px INT,
  height_px INT,
  capture_exposure_ms DOUBLE,
  schema_version STRING,
  event_date DATE
) USING DELTA;
COMMENT ON TABLE prism.silver.camera_frames IS 'Typed camera-frame metadata from bronze JSON.';
ALTER TABLE prism.silver.camera_frames SET TBLPROPERTIES (
  'quality.expectations_source' = 'lakehouse/quality/expectations.yaml',
  'quality.expectation.asset_id_not_null' = 'asset_id IS NOT NULL',
  'quality.expectation.asset_id_not_null.action' = 'fail',
  'quality.expectation.frame_id_not_null' = 'frame_id IS NOT NULL',
  'quality.expectation.frame_id_not_null.action' = 'fail',
  'quality.expectation.timestamp_not_null' = 'event_ts IS NOT NULL',
  'quality.expectation.timestamp_not_null.action' = 'fail',
  'quality.expectation.width_positive' = 'width_px >= 1',
  'quality.expectation.width_positive.action' = 'drop',
  'quality.expectation.height_positive' = 'height_px >= 1',
  'quality.expectation.height_positive.action' = 'drop',
  'quality.expectation.storage_uri_scheme' = 'storage_uri RLIKE ''^(s3|file)://''',
  'quality.expectation.storage_uri_scheme.action' = 'drop'
);

CREATE TABLE IF NOT EXISTS prism.gold.asset_daily_metrics (
  asset_id STRING,
  metric_date DATE,
  ping_count BIGINT,
  avg_speed_mph DOUBLE,
  max_speed_mph DOUBLE,
  avg_fuel_level_pct DOUBLE,
  max_odometer_km DOUBLE,
  first_event_ts TIMESTAMP,
  last_event_ts TIMESTAMP
) USING DELTA;
COMMENT ON TABLE prism.gold.asset_daily_metrics IS 'Per-asset daily aggregates over silver sensor pings.';
ALTER TABLE prism.gold.asset_daily_metrics SET TBLPROPERTIES (
  'quality.expectations_source' = 'lakehouse/quality/expectations.yaml',
  'quality.expectation.asset_id_not_null' = 'asset_id IS NOT NULL',
  'quality.expectation.asset_id_not_null.action' = 'fail',
  'quality.expectation.metric_date_not_null' = 'metric_date IS NOT NULL',
  'quality.expectation.metric_date_not_null.action' = 'fail',
  'quality.expectation.ping_count_positive' = 'ping_count >= 0',
  'quality.expectation.ping_count_positive.action' = 'fail',
  'quality.expectation.avg_speed_range' = 'avg_speed_mph IS NULL OR (avg_speed_mph BETWEEN 0 AND 120)',
  'quality.expectation.avg_speed_range.action' = 'drop'
);

CREATE TABLE IF NOT EXISTS prism.gold.fleet_frame_summary (
  asset_id STRING,
  metric_date DATE,
  frame_count BIGINT,
  camera_device_count BIGINT,
  first_frame_ts TIMESTAMP,
  last_frame_ts TIMESTAMP
) USING DELTA;
COMMENT ON TABLE prism.gold.fleet_frame_summary IS 'Per-asset daily camera-frame counts.';
ALTER TABLE prism.gold.fleet_frame_summary SET TBLPROPERTIES (
  'quality.expectations_source' = 'lakehouse/quality/expectations.yaml',
  'quality.expectation.asset_id_not_null' = 'asset_id IS NOT NULL',
  'quality.expectation.asset_id_not_null.action' = 'fail',
  'quality.expectation.metric_date_not_null' = 'metric_date IS NOT NULL',
  'quality.expectation.metric_date_not_null.action' = 'fail',
  'quality.expectation.frame_count_nonneg' = 'frame_count >= 0',
  'quality.expectation.frame_count_nonneg.action' = 'fail'
);

GRANT USE CATALOG ON CATALOG prism TO `account users`;
GRANT USE SCHEMA ON SCHEMA prism.bronze TO `account users`;
GRANT USE SCHEMA ON SCHEMA prism.silver TO `account users`;
GRANT USE SCHEMA ON SCHEMA prism.gold TO `account users`;
GRANT SELECT ON SCHEMA prism.gold TO `prism-viewers`;
GRANT SELECT, MODIFY ON SCHEMA prism.silver TO `prism-engineers`;
GRANT ALL PRIVILEGES ON CATALOG prism TO `prism-admins`;

-- Expectation property prefix in use: quality.expectation.
