"""Environment configuration for the AI copilot."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class CopilotConfig:
    port: int = 9104
    activation_url: str = "http://127.0.0.1:9103"
    control_plane_url: str = "http://127.0.0.1:9100"
    incident_engine_url: str = "http://127.0.0.1:9108"
    control_plane_token: str = ""
    cv_findings_gold_dir: Path = Path(".data/lakehouse/gold/cv_findings")
    cors_origins: tuple[str, ...] = (
        "http://localhost:9101",
        "http://127.0.0.1:9101",
    )

    @classmethod
    def from_env(cls) -> CopilotConfig:
        origins = tuple(
            o.strip()
            for o in os.environ.get(
                "PRISM_CORS_ORIGINS",
                "http://localhost:9101,http://127.0.0.1:9101",
            ).split(",")
            if o.strip()
        )
        data = Path(os.environ.get("PRISM_DATA_ROOT", ".data"))
        gold = Path(
            os.environ.get(
                "PRISM_CV_FINDINGS_GOLD_DIR",
                str(data / "lakehouse" / "gold" / "cv_findings"),
            )
        )
        return cls(
            port=int(os.environ.get("PRISM_AI_COPILOT_PORT", "9104")),
            activation_url=os.environ.get("PRISM_ACTIVATION_URL", "http://127.0.0.1:9103").rstrip(
                "/"
            ),
            control_plane_url=os.environ.get(
                "PRISM_CONTROL_PLANE_URL", "http://127.0.0.1:9100"
            ).rstrip("/"),
            incident_engine_url=os.environ.get(
                "PRISM_INCIDENT_ENGINE_URL", "http://127.0.0.1:9108"
            ).rstrip("/"),
            control_plane_token=os.environ.get("PRISM_CONTROL_PLANE_TOKEN", "").strip(),
            cv_findings_gold_dir=gold,
            cors_origins=origins or cls.cors_origins,
        )
