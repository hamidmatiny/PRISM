"""Drift statistics: KS test on numeric features, embedding-style centroid
distance, and KS test on vector norms -- sentinel-ray's ``drift_detector.py``
math, ported near-verbatim per the release plan's lineage table.

One documented, deliberate deviation from sentinel-ray: sentinel-ray's
embedding tests assumed a deep-model embedding vector. PRISM's actual
cv-service (``cv-service/src/prism_cv_service/detector.py``) is a bounding-box
YOLO-style ONNX decoder with no embedding head -- there is no deep embedding
anywhere in this codebase to compare. Rather than fabricate one (ADR-005:
"a subsystem may not claim a capability it hasn't earned the evidence for"),
this module runs the exact same centroid-distance and norm-KS math against a
real, low-dimensional feature vector genuinely computed from CV detector
output (confidence, box geometry, one-hot defect class) -- see
``cv_finding_vector`` in ``features.py``. It is honestly labeled a "CV
finding feature vector", never called an "embedding", anywhere in this
service's code, API responses, or docs.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from scipy import stats

DEFAULT_KS_ALPHA = 0.05
DEFAULT_CENTROID_Z = 2.5


@dataclass(frozen=True)
class FeatureTestResult:
    feature: str
    test: str  # "ks_feature" | "centroid_distance" | "ks_norm"
    drifted: bool
    statistic: float
    detail: dict[str, float]


def ks_per_feature(
    baseline: dict[str, list[float]],
    window: dict[str, list[float]],
    *,
    alpha: float = DEFAULT_KS_ALPHA,
) -> list[FeatureTestResult]:
    """Two-sample Kolmogorov-Smirnov test, independently, per numeric feature.

    A feature counts as drifted when its distribution in the current window
    is statistically distinguishable (p < alpha) from the frozen baseline
    distribution of that same feature. Requires at least 2 samples on each
    side -- scipy's ks_2samp is undefined below that.
    """
    results: list[FeatureTestResult] = []
    for name, base_values in baseline.items():
        win_values = window.get(name)
        if not win_values or len(base_values) < 2 or len(win_values) < 2:
            continue
        ks = stats.ks_2samp(base_values, win_values)
        results.append(
            FeatureTestResult(
                feature=name,
                test="ks_feature",
                drifted=bool(ks.pvalue < alpha),
                statistic=float(ks.statistic),
                detail={"pvalue": float(ks.pvalue), "alpha": alpha},
            )
        )
    return results


def centroid_distance(
    baseline_vectors: list[list[float]],
    window_vectors: list[list[float]],
    *,
    z: float = DEFAULT_CENTROID_Z,
) -> FeatureTestResult:
    """Euclidean distance between the baseline centroid and the current
    window's centroid, scaled against the baseline's own per-dimension
    spread (``z`` standard-deviation-norm multiples away counts as drifted).

    A fixed absolute distance threshold would be meaningless across features
    with different natural scales; scaling by the baseline's own spread
    keeps this comparable across differently-scaled vectors.
    """
    base = np.asarray(baseline_vectors, dtype=float)
    win = np.asarray(window_vectors, dtype=float)
    base_centroid = base.mean(axis=0)
    win_centroid = win.mean(axis=0)
    distance = float(np.linalg.norm(win_centroid - base_centroid))
    spread = float(np.linalg.norm(base.std(axis=0))) or 1e-9
    threshold = z * spread
    return FeatureTestResult(
        feature="__centroid__",
        test="centroid_distance",
        drifted=bool(distance > threshold),
        statistic=distance,
        detail={"threshold": threshold, "spread": spread, "z": z},
    )


def ks_on_norms(
    baseline_vectors: list[list[float]],
    window_vectors: list[list[float]],
    *,
    alpha: float = DEFAULT_KS_ALPHA,
) -> FeatureTestResult:
    """KS test on the *scalar* distribution of vector norms (magnitudes),
    baseline vs current window -- catches a shift in overall vector
    "energy" that a per-dimension test could miss (e.g. every dimension
    moves a little vs. one dimension moving a lot)."""
    base_norms = np.linalg.norm(np.asarray(baseline_vectors, dtype=float), axis=1).tolist()
    win_norms = np.linalg.norm(np.asarray(window_vectors, dtype=float), axis=1).tolist()
    ks = stats.ks_2samp(base_norms, win_norms)
    return FeatureTestResult(
        feature="__norm__",
        test="ks_norm",
        drifted=bool(ks.pvalue < alpha),
        statistic=float(ks.statistic),
        detail={"pvalue": float(ks.pvalue), "alpha": alpha},
    )
