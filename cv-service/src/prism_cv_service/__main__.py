"""CLI: ``python -m prism_cv_service``."""

from __future__ import annotations

import argparse
import logging

import uvicorn

from prism_cv_service.api import create_app
from prism_cv_service.config import CvConfig


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="PRISM CV inference service")
    parser.add_argument("--host", default=None)
    parser.add_argument("--port", type=int, default=None)
    args = parser.parse_args(argv)

    logging.basicConfig(level=logging.INFO)
    config = CvConfig.from_env()
    host = args.host or config.host
    port = args.port or config.port
    app = create_app(config)
    uvicorn.run(app, host=host, port=port, log_level="info")


if __name__ == "__main__":
    main()
