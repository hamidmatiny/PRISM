# CV models

| Artifact | Role |
|----------|------|
| `yolo_fleet_defects_tiny.onnx` | Tiny YOLO-family head (CPU). Input `[1,3,320,320]`, output `[1,9,100]`. |
| `labels.json` | Class id → defect name mapping |

Regenerate:

```bash
python cv-service/scripts/export_tiny_yolo_onnx.py
```

Never run GPU inference in CI (ADR-001).
