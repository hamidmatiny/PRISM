# Fleet defect label set

Coherent label taxonomy for PRISM CV findings. These map 1:1 to
`contracts/cv-finding-schema` `DefectClass` values.

| Class id | Enum value | Meaning (fleet ops) |
|----------|------------|---------------------|
| 0 | `dent` | Body-panel deformation / impact dent |
| 1 | `crack` | Structural or glass crack |
| 2 | `tire_wear` | Abnormal tire tread / sidewall wear |
| 3 | `sensor_obstruction` | Camera/LiDAR/radar aperture blocked or dirty |
| 4 | `anomaly` | Catch-all defect/anomaly not in the above set |

## Discipline

- Tests assert **schema-valid, confidence-bounded** outputs only.
- They do **not** claim real-world detection accuracy, mAP, or recall.
- Low-confidence detections (`confidence < threshold`) are routed to the
  human-review queue — never auto-published as actionable findings.
