"""Run activation-gateway (+ embedded mock warehouses in mock mode)."""

from __future__ import annotations

import httpx
import uvicorn

from prism_activation_gateway.api import create_app
from prism_activation_gateway.config import GatewayConfig
from prism_activation_gateway.mock_servers import start_embedded_mocks, wait_until_healthy


def main() -> None:
    config = GatewayConfig.from_env()
    if config.mode == "mock" and config.start_embedded_mocks:
        start_embedded_mocks(
            redshift_url=config.redshift_endpoint,
            snowflake_url=config.snowflake_endpoint,
        )
        with httpx.Client() as client:
            wait_until_healthy(client, config.redshift_endpoint)
            wait_until_healthy(client, config.snowflake_endpoint)

    app = create_app(config)
    uvicorn.run(app, host="0.0.0.0", port=config.port, log_level="info")


if __name__ == "__main__":
    main()
