"""Minimal health HTTP server for the ingestion service."""

from __future__ import annotations

import json
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from prism_ingestion.pipeline import IngestPipeline


def start_health_server(pipeline: IngestPipeline, host: str, port: int) -> ThreadingHTTPServer:
    ingest_pipeline = pipeline

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, format: str, *args: object) -> None:  # noqa: A003
            return

        def do_GET(self) -> None:  # noqa: N802
            if self.path not in {"/health", "/healthz"}:
                self.send_response(404)
                self.end_headers()
                return
            body = {
                "status": "ok",
                "service": "ingestion",
                "backend": ingest_pipeline.config.backend,
                "stats": ingest_pipeline.stats.as_dict(),
            }
            payload = json.dumps(body).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(payload)))
            self.end_headers()
            self.wfile.write(payload)

    server = ThreadingHTTPServer((host, port), Handler)
    thread = threading.Thread(target=server.serve_forever, name="ingestion-health", daemon=True)
    thread.start()
    return server
