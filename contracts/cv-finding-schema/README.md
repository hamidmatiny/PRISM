# cv-finding-schema

Defect/anomaly finding contract for CV outputs and the control-plane review workflow.

| Model | JSON Schema | Purpose |
|-------|-------------|---------|
| `CvFinding` | `schemas/cv_finding.schema.json` | One detection tied to asset + frame |

## Fields

- `finding_id` — `fnd_[0-9a-f]{12}`
- `asset_id` — `PRISM-AST-\d{3}`
- `frame_ref` — `frm_[0-9a-f]{12}`
- `defect_class` — `dent` \| `crack` \| `tire_wear` \| `sensor_obstruction` \| `anomaly`
- `confidence` — `[0.0, 1.0]`
- `bounding_box` — optional pixel AABB
- `segmentation_mask_ref` — optional `s3://` or `file://`
- `reviewed` — human-review flag (consumed in Phase 5)

## Install / use

```bash
pip install -e contracts/cv-finding-schema
python -m prism_cv_finding_schema.export
```

**Health / port:** N/A (library package). CV service that emits findings lands in Phase 3.
