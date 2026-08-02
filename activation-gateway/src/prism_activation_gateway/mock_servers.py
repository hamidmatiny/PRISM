"""Embed mock Redshift + Snowflake HTTP endpoints beside the gateway."""

from __future__ import annotations

import threading
from dataclasses import dataclass
from typing import Any
from urllib.parse import urlparse

import uvicorn

from prism_activation_gateway.mocks.redshift_endpoint import create_redshift_mock_app
from prism_activation_gateway.mocks.snowflake_endpoint import create_snowflake_mock_app


@dataclass
class EmbeddedMocks:
    redshift_thread: threading.Thread
    snowflake_thread: threading.Thread
    redshift_url: str
    snowflake_url: str


def _port(url: str) -> int:
    parsed = urlparse(url)
    if parsed.port is None:
        raise ValueError(f"mock URL must include a port: {url}")
    return parsed.port


def start_embedded_mocks(*, redshift_url: str, snowflake_url: str) -> EmbeddedMocks:
    """Start mock warehouse uvicorn servers in daemon threads."""
    rs_app = create_redshift_mock_app()
    sf_app = create_snowflake_mock_app()

    rs_config = uvicorn.Config(
        rs_app,
        host="0.0.0.0",
        port=_port(redshift_url),
        log_level="warning",
    )
    sf_config = uvicorn.Config(
        sf_app,
        host="0.0.0.0",
        port=_port(snowflake_url),
        log_level="warning",
    )
    rs_server = uvicorn.Server(rs_config)
    sf_server = uvicorn.Server(sf_config)

    rs_thread = threading.Thread(target=rs_server.run, name="mock-redshift", daemon=True)
    sf_thread = threading.Thread(target=sf_server.run, name="mock-snowflake", daemon=True)
    rs_thread.start()
    sf_thread.start()
    return EmbeddedMocks(
        redshift_thread=rs_thread,
        snowflake_thread=sf_thread,
        redshift_url=redshift_url,
        snowflake_url=snowflake_url,
    )


def wait_until_healthy(client: Any, url: str, *, attempts: int = 50) -> None:
    import time

    for _ in range(attempts):
        try:
            response = client.get(f"{url.rstrip('/')}/health", timeout=0.5)
            if response.status_code == 200:
                return
        except Exception:  # noqa: BLE001 — retry loop
            pass
        time.sleep(0.05)
    raise RuntimeError(f"mock warehouse not healthy: {url}")
