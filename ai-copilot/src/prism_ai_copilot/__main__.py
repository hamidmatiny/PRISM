"""CLI entry: uvicorn on :9104."""

from __future__ import annotations

import uvicorn

from prism_ai_copilot.api import create_app
from prism_ai_copilot.config import CopilotConfig


def main() -> None:
    cfg = CopilotConfig.from_env()
    app = create_app(cfg)
    uvicorn.run(app, host="0.0.0.0", port=cfg.port, log_level="info")


if __name__ == "__main__":
    main()
