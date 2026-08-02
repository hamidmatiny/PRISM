"""CloudWatch EMF helpers — emit ReviewQueueDepth when running on AWS."""

from __future__ import annotations

import json
import os
import sys
from typing import Any


def emit_review_queue_depth(depth: int) -> None:
    """Write Embedded Metric Format to stdout for CloudWatch Logs agent / awslogs."""
    if os.environ.get("PRISM_ENV", "").lower() != "aws" and os.environ.get(
        "PRISM_EMIT_EMF", ""
    ).lower() not in {"1", "true", "yes"}:
        return
    payload: dict[str, Any] = {
        "_aws": {
            "Timestamp": int(__import__("time").time() * 1000),
            "CloudWatchMetrics": [
                {
                    "Namespace": "PRISM",
                    "Dimensions": [["Service"]],
                    "Metrics": [{"Name": "ReviewQueueDepth", "Unit": "Count"}],
                }
            ],
        },
        "Service": "control-plane",
        "ReviewQueueDepth": int(depth),
    }
    print(json.dumps(payload), file=sys.stdout, flush=True)
