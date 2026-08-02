# Activation gold fixtures

Small labeled Parquet gold tables for local / CI activation (structural only).

| Table | Rows | Purpose |
|-------|------|---------|
| `gold/asset_daily_metrics/` | 3 | Conformance activate+query |
| `gold/fleet_frame_summary/` | 2 | Secondary table smoke |

These are **not** claims about production volumes. Same discipline as Vulcan: assert structural equivalence across adapters, not invented warehouse throughput.
