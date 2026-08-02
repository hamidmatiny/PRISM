{{ config(alias="sensor_pings") }}

select
  asset_id,
  device_id,
  cast(event_ts as timestamp) as event_ts,
  cast(speed_mph as double) as speed_mph,
  cast(latitude as double) as latitude,
  cast(longitude as double) as longitude,
  cast(heading_deg as double) as heading_deg,
  cast(odometer_km as double) as odometer_km,
  cast(fuel_level_pct as double) as fuel_level_pct,
  schema_version,
  cast(event_date as date) as event_date
from {{ silver_relation("sensor_pings") }}
