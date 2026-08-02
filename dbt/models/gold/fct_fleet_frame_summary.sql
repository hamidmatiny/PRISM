{{ config(alias="fleet_frame_summary", materialized="table") }}

-- depends_on: {{ ref('dim_assets') }}

select
  asset_id,
  event_date as metric_date,
  count(*)::bigint as frame_count,
  count(distinct device_id)::bigint as camera_device_count,
  min(event_ts) as first_frame_ts,
  max(event_ts) as last_frame_ts
from {{ ref("stg_camera_frames") }}
group by asset_id, event_date
