{{ config(alias="camera_frames") }}

select
  asset_id,
  device_id,
  frame_id,
  cast(event_ts as timestamp) as event_ts,
  storage_uri,
  content_type,
  cast(width_px as integer) as width_px,
  cast(height_px as integer) as height_px,
  cast(capture_exposure_ms as double) as capture_exposure_ms,
  schema_version,
  cast(event_date as date) as event_date
from {{ silver_relation("camera_frames") }}
