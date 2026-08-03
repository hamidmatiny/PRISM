"""CLI entry: uvicorn on :9109."""

from __future__ import annotations

import uvicorn

from prism_drift_monitor.api import create_app
from prism_drift_monitor.config import DriftConfig


def main() -> None:
    cfg = DriftConfig.from_env()
    app = create_app(cfg)
    uvicorn.run(app, host=cfg.host, port=cfg.port, log_level="info")


if __name__ == "__main__":
    main()
