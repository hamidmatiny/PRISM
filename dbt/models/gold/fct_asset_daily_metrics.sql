{{ config(alias="asset_daily_metrics", materialized="table") }}

-- depends_on: {{ ref('dim_assets') }}

select
  asset_id,
  event_date as metric_date,
  count(*)::bigint as ping_count,
  avg(speed_mph) as avg_speed_mph,
  max(speed_mph) as max_speed_mph,
  avg(fuel_level_pct) as avg_fuel_level_pct,
  max(odometer_km) as max_odometer_km,
  min(event_ts) as first_event_ts,
  max(event_ts) as last_event_ts
from {{ ref("stg_sensor_pings") }}
group by asset_id, event_date
