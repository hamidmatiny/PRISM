{{ config(alias="assets", materialized="table") }}

with sensors as (
  select distinct asset_id from {{ ref("stg_sensor_pings") }}
),
frames as (
  select distinct asset_id from {{ ref("stg_camera_frames") }}
)

select
  coalesce(s.asset_id, f.asset_id) as asset_id,
  (s.asset_id is not null) as has_sensor_telemetry,
  (f.asset_id is not null) as has_camera_frames
from sensors s
full outer join frames f on s.asset_id = f.asset_id
