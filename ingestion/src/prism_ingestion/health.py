"""Minimal HTTP server for the ingestion service: health + admin endpoints."""

from __future__ import annotations

import json
import logging
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import TYPE_CHECKING

from prism_ingestion.scenario_run import ScenarioRunError, run_scenario_batch

if TYPE_CHECKING:
    from prism_ingestion.pipeline import IngestPipeline

logger = logging.getLogger(__name__)


def start_health_server(pipeline: IngestPipeline, host: str, port: int) -> ThreadingHTTPServer:
    ingest_pipeline = pipeline

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, format: str, *args: object) -> None:  # noqa: A003
            return

        def do_GET(self) -> None:  # noqa: N802
            if self.path not in {"/health", "/healthz"}:
                self._send_json(404, {"error": "not found"})
                return
            body = {
                "status": "ok",
                "service": "ingestion",
                "backend": ingest_pipeline.config.backend,
                "source_mode": ingest_pipeline.config.source_mode,
                "scenario_url": ingest_pipeline.config.scenario_url,
                "stats": ingest_pipeline.stats.as_dict(),
            }
            self._send_json(200, body)

        def do_POST(self) -> None:  # noqa: N802
            if self.path != "/v1/scenario-runs":
                self._send_json(404, {"error": "not found"})
                return
            length = int(self.headers.get("Content-Length", "0") or "0")
            raw = self.rfile.read(length) if length else b"{}"
            try:
                req = json.loads(raw or b"{}")
            except json.JSONDecodeError:
                self._send_json(400, {"error": "invalid JSON body"})
                return
            if "seed" not in req:
                self._send_json(400, {"error": "'seed' is required"})
                return
            try:
                seed = int(req["seed"])
                ticks = int(req.get("ticks", 30))
                rate_hz = float(req.get("rate_hz", 3.0))
                scenario_id = req.get("scenario_id")
            except (TypeError, ValueError) as exc:
                self._send_json(400, {"error": f"bad request body: {exc}"})
                return
            try:
                result = run_scenario_batch(
                    ingest_pipeline.config,
                    seed=seed,
                    ticks=ticks,
                    rate_hz=rate_hz,
                    scenario_id=scenario_id,
                )
            except ScenarioRunError as exc:
                logger.warning("scenario-run request rejected: %s", exc)
                self._send_json(400, {"error": str(exc)})
                return
            self._send_json(200, result)

        def _send_json(self, status: int, body: dict[str, object]) -> None:
            payload = json.dumps(body).encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(payload)))
            self.end_headers()
            self.wfile.write(payload)

    server = ThreadingHTTPServer((host, port), Handler)
    thread = threading.Thread(target=server.serve_forever, name="ingestion-health", daemon=True)
    thread.start()
    return server
