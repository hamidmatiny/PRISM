#!/usr/bin/env python3
"""Generate small synthetic labeled sample images (structural fixtures only)."""

from __future__ import annotations

import json
from pathlib import Path

import cv2
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "fixtures" / "images"
META = ROOT / "fixtures" / "manifest.json"

# Colors are decorative only — not a claim that the model detects them.
SAMPLES = [
    ("dent_sample.png", "dent", (40, 40, 200)),
    ("crack_sample.png", "crack", (200, 40, 40)),
    ("tire_wear_sample.png", "tire_wear", (40, 200, 40)),
    ("sensor_obstruction_sample.png", "sensor_obstruction", (200, 200, 40)),
    ("anomaly_sample.png", "anomaly", (200, 40, 200)),
]


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    entries = []
    for name, label, color in SAMPLES:
        img = np.full((240, 320, 3), 30, dtype=np.uint8)
        cv2.rectangle(img, (60, 50), (220, 180), color, thickness=-1)
        cv2.putText(
            img,
            label,
            (70, 120),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.7,
            (255, 255, 255),
            2,
        )
        path = OUT / name
        cv2.imwrite(str(path), img)
        entries.append(
            {
                "file": f"images/{name}",
                "intended_label": label,
                "note": "Synthetic fixture for structural tests — not a ground-truth accuracy set",
            }
        )
    META.write_text(json.dumps({"fixtures": entries}, indent=2) + "\n", encoding="utf-8")
    print(f"wrote {len(entries)} fixtures under {OUT}")


if __name__ == "__main__":
    main()
