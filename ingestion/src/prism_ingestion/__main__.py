"""CLI entrypoint: ``python -m prism_ingestion``."""

from __future__ import annotations

import argparse
import logging
import signal
import sys

from prism_ingestion.config import IngestConfig
from prism_ingestion.health import start_health_server
from prism_ingestion.pipeline import IngestPipeline


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="PRISM fleet ingestion simulator")
    parser.add_argument(
        "--duration",
        type=float,
        default=None,
        help="Override PRISM_DURATION_SECONDS (0 = run forever).",
    )
    parser.add_argument(
        "--rate",
        type=float,
        default=None,
        help="Override PRISM_EMIT_RATE (events/sec).",
    )
    parser.add_argument(
        "--failure-rate",
        type=float,
        default=None,
        help="Override PRISM_FAILURE_RATE.",
    )
    parser.add_argument(
        "--backend",
        choices=("file", "localstack"),
        default=None,
        help="Override PRISM_INGEST_BACKEND.",
    )
    parser.add_argument(
        "--no-health",
        action="store_true",
        help="Disable the /health HTTP server.",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )
    args = _build_parser().parse_args(argv)
    config = IngestConfig.from_env()
    # dataclasses.replace alternative for frozen config
    overrides: dict = {}
    if args.duration is not None:
        overrides["duration_seconds"] = args.duration
    if args.rate is not None:
        overrides["emit_rate_hz"] = args.rate
    if args.failure_rate is not None:
        overrides["failure_rate"] = args.failure_rate
    if args.backend is not None:
        overrides["backend"] = args.backend
    if overrides:
        config = IngestConfig(**{**config.__dict__, **overrides})

    try:
        from prism_otel import setup_tracing

        setup_tracing("ingestion")
    except ImportError:
        pass

    pipeline = IngestPipeline.from_config(config)
    server = None
    if not args.no_health:
        server = start_health_server(pipeline, config.health_host, config.health_port)
        logging.getLogger(__name__).info(
            "Health server listening on %s:%s",
            config.health_host,
            config.health_port,
        )

    def _handle_stop(signum: int, _frame: object) -> None:
        logging.getLogger(__name__).info("Received signal %s — stopping", signum)
        pipeline.stop()

    signal.signal(signal.SIGINT, _handle_stop)
    signal.signal(signal.SIGTERM, _handle_stop)

    stats = pipeline.run()
    if server is not None:
        server.shutdown()
    logging.getLogger(__name__).info("Final stats: %s", stats.as_dict())
    return 0


if __name__ == "__main__":
    sys.exit(main())
