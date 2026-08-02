"""OpenCV preprocessing: resize, denoise, contrast normalization."""

from __future__ import annotations

from os import PathLike

import cv2
import numpy as np


def load_bgr_image(path_or_bytes: str | bytes | PathLike) -> np.ndarray:
    if isinstance(path_or_bytes, (bytes, bytearray)):
        arr = np.frombuffer(path_or_bytes, dtype=np.uint8)
        image = cv2.imdecode(arr, cv2.IMREAD_COLOR)
        if image is None:
            raise ValueError("failed to decode image bytes")
        return image
    image = cv2.imread(str(path_or_bytes), cv2.IMREAD_COLOR)
    if image is None:
        raise ValueError(f"failed to read image: {path_or_bytes}")
    return image


def preprocess_bgr(
    image_bgr: np.ndarray,
    *,
    input_size: tuple[int, int] = (320, 320),
) -> tuple[np.ndarray, dict[str, float | int]]:
    """
    Resize → bilateral denoise → CLAHE contrast normalize → NCHW float32 [0,1].

    Returns ``(batch_tensor, meta)`` where meta includes original HxW for box mapping.
    """
    if image_bgr.ndim != 3 or image_bgr.shape[2] != 3:
        raise ValueError("expected BGR HxWx3 image")

    orig_h, orig_w = image_bgr.shape[:2]
    target_w, target_h = input_size

    resized = cv2.resize(image_bgr, (target_w, target_h), interpolation=cv2.INTER_AREA)
    denoised = cv2.bilateralFilter(resized, d=5, sigmaColor=50, sigmaSpace=50)

    lab = cv2.cvtColor(denoised, cv2.COLOR_BGR2LAB)
    l_chan, a_chan, b_chan = cv2.split(lab)
    clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
    l_chan = clahe.apply(l_chan)
    normalized = cv2.cvtColor(cv2.merge([l_chan, a_chan, b_chan]), cv2.COLOR_LAB2BGR)

    rgb = cv2.cvtColor(normalized, cv2.COLOR_BGR2RGB).astype(np.float32) / 255.0
    nchw = np.transpose(rgb, (2, 0, 1))[None, ...]
    meta: dict[str, float | int] = {
        "orig_width": int(orig_w),
        "orig_height": int(orig_h),
        "input_width": int(target_w),
        "input_height": int(target_h),
    }
    return nchw, meta
