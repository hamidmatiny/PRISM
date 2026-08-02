"""CLI entry: uvicorn on :9108."""

from __future__ import annotations

import uvicorn

from prism_incident_engine.api import create_app
from prism_incident_engine.config import IncidentConfig


def main() -> None:
    cfg = IncidentConfig.from_env()
    app = create_app(cfg)
    uvicorn.run(app, host=cfg.host, port=cfg.port, log_level="info")


if __name__ == "__main__":
    main()
