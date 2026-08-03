"""Feature extraction: what a "feature group" actually contains.

Two groups, matching the two real, non-fabricated signal sources PRISM's
pipeline can produce (see detector.py's module docstring for why there's no
third, embedding-based group):

* ``telemetry_numeric`` -- the numeric fields of a real, contract-valid
  ``SensorPing`` (speed_mph, latitude, longitude, heading_deg, odometer_km,
  fuel_level_pct). ``ks_per_feature`` runs independently on each.
* ``cv_geometry`` -- a real, low-dimensional feature vector computed from a
  genuine cv-service detection (confidence, box width/height/aspect ratio,
  one-hot defect class). ``centroid_distance`` + ``ks_on_norms`` run on this
  as a vector. Honestly labeled a "feature vector", never an "embedding" --
  see detector.py.
"""

from __future__ import annotations

# odometer_km is deliberately excluded: it is a monotonically increasing
# cumulative counter (see ingestion's FleetSimulator and scenario-engine's
# sampler.py, both of which only ever add to it tick over tick), never a
# stationary distribution. A KS test against two different time windows of
# a monotonic counter would "detect drift" on every single run regardless
# of any actual anomaly -- it would just be measuring elapsed time. Caught
# during this phase's build (empirically: a local smoke test showed
# odometer_km "drifting" on the very first comparison window, before any
# real shift was introduced), not reported after the fact.
TELEMETRY_NUMERIC_FIELDS = (
    "speed_mph",
    "latitude",
    "longitude",
    "heading_deg",
    "fuel_level_pct",
)

DEFECT_CLASSES = ("dent", "crack", "tire_wear", "sensor_obstruction", "anomaly")


def telemetry_numeric_features(payload: dict) -> dict[str, float]:
    """Extract the numeric feature dict from a validated SensorPing payload.
    Missing/non-numeric fields are simply omitted (fuel_level_pct is
    optional in the schema itself)."""
    out: dict[str, float] = {}
    for field in TELEMETRY_NUMERIC_FIELDS:
        value = payload.get(field)
        if isinstance(value, (int, float)) and not isinstance(value, bool):
            out[field] = float(value)
    return out


def cv_geometry_vector(finding: dict) -> list[float]:
    """Real, low-dimensional feature vector from a genuine CvFinding payload
    -- confidence, box width, box height, aspect ratio, one-hot defect class.
    Not a deep embedding (PRISM's cv-service has no embedding head); see
    detector.py's module docstring."""
    box = finding.get("bounding_box") or {}
    width = float(box.get("width", 0.0))
    height = float(box.get("height", 0.0))
    aspect = width / height if height > 0 else 0.0
    confidence = float(finding.get("confidence", 0.0))
    defect_class = finding.get("defect_class")
    one_hot = [1.0 if defect_class == name else 0.0 for name in DEFECT_CLASSES]
    return [confidence, width, height, aspect, *one_hot]
