"""CLI entry: uvicorn on :9107."""

from __future__ import annotations

import uvicorn

from prism_scenario_engine.api import create_app
from prism_scenario_engine.config import ScenarioConfig


def main() -> None:
    cfg = ScenarioConfig.from_env()
    app = create_app(cfg)
    uvicorn.run(app, host=cfg.host, port=cfg.port, log_level="info")


if __name__ == "__main__":
    main()
