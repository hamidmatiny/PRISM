#!/usr/bin/env python3
"""Export a tiny YOLO-family ONNX model for CPU-dev / CI (ADR-001).

Output layout matches a compact YOLOv8-style head:
  input:  float32[1, 3, 320, 320]
  output: float32[1, 4+num_classes, num_anchors]
          channels = [cx, cy, w, h, class_0..class_n]

This model is intentionally tiny and deterministic. It is **not** trained on
real defects and must never be cited for accuracy claims.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import onnx
from onnx import TensorProto, helper, numpy_helper

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "models" / "yolo_fleet_defects_tiny.onnx"

NUM_CLASSES = 5
NUM_ANCHORS = 100
INPUT_H = 320
INPUT_W = 320
OUT_CHANNELS = 4 + NUM_CLASSES  # 9


def build() -> onnx.ModelProto:
    inp = helper.make_tensor_value_info("images", TensorProto.FLOAT, [1, 3, INPUT_H, INPUT_W])
    out = helper.make_tensor_value_info(
        "output0", TensorProto.FLOAT, [1, OUT_CHANNELS, NUM_ANCHORS]
    )

    packed = np.zeros((NUM_ANCHORS, OUT_CHANNELS), dtype=np.float32)
    for i in range(NUM_ANCHORS):
        packed[i, 0] = 0.2 + (i % 10) * 0.06
        packed[i, 1] = 0.2 + (i // 10) * 0.06
        packed[i, 2] = 0.15
        packed[i, 3] = 0.12
        packed[i, 4 + (i % NUM_CLASSES)] = 0.35 + (i % 5) * 0.05

    flat = packed.reshape(-1)  # [A*C] == 900
    mean_scale = np.array([0.4, 0.4, 0.4], dtype=np.float32)
    # Gemm: Y[1,900] = pooled[1,3] @ W[3,900] + B[900]
    w = np.outer(mean_scale / 3.0, flat * 0.15).astype(np.float32)
    bias = flat.copy()
    assert w.shape == (3, OUT_CHANNELS * NUM_ANCHORS), w.shape

    nodes = [
        helper.make_node("GlobalAveragePool", ["images"], ["pooled"]),
        helper.make_node("Reshape", ["pooled", "shape_in"], ["pooled_flat"]),
        helper.make_node("Gemm", ["pooled_flat", "W", "B"], ["flat_out"], alpha=1.0, beta=1.0),
        helper.make_node("Reshape", ["flat_out", "shape_mid"], ["reshaped"]),
        helper.make_node("Transpose", ["reshaped"], ["output0"], perm=[0, 2, 1]),
    ]

    graph = helper.make_graph(
        nodes,
        "yolo_fleet_defects_tiny",
        [inp],
        [out],
        initializer=[
            numpy_helper.from_array(w, name="W"),
            numpy_helper.from_array(bias, name="B"),
            numpy_helper.from_array(np.array([1, 3], dtype=np.int64), name="shape_in"),
            numpy_helper.from_array(
                np.array([1, NUM_ANCHORS, OUT_CHANNELS], dtype=np.int64), name="shape_mid"
            ),
        ],
    )
    model = helper.make_model(
        graph,
        opset_imports=[helper.make_opsetid("", 17)],
        producer_name="prism-cv-service",
    )
    model.ir_version = 8
    onnx.checker.check_model(model)
    return model


def main() -> None:
    OUT.parent.mkdir(parents=True, exist_ok=True)
    model = build()
    onnx.save(model, str(OUT))
    # Smoke: session run
    import onnxruntime as ort

    sess = ort.InferenceSession(str(OUT), providers=["CPUExecutionProvider"])
    x = np.zeros((1, 3, INPUT_H, INPUT_W), dtype=np.float32)
    y = sess.run(None, {"images": x})[0]
    assert y.shape == (1, OUT_CHANNELS, NUM_ANCHORS), y.shape
    print(f"wrote {OUT} ({OUT.stat().st_size} bytes) output_shape={y.shape}")


if __name__ == "__main__":
    main()
