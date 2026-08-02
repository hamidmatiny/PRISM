"""Local mocked warehouse HTTP endpoints (ADR-001 — no real cloud)."""

from prism_activation_gateway.mocks.redshift_endpoint import create_redshift_mock_app
from prism_activation_gateway.mocks.snowflake_endpoint import create_snowflake_mock_app

__all__ = ["create_redshift_mock_app", "create_snowflake_mock_app"]
