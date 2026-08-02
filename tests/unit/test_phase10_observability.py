"""Phase 10 — OTel helpers, security docs, secrets rotation loop closed."""

from __future__ import annotations

import os
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def test_prism_otel_noop_without_endpoint() -> None:
    os.environ.pop("OTEL_EXPORTER_OTLP_ENDPOINT", None)
    os.environ["OTEL_SDK_DISABLED"] = "false"
    from prism_otel import setup_tracing
    from prism_otel.setup import _enabled

    assert _enabled() is False
    assert setup_tracing("unit-test") is False


def test_prism_otel_disabled_flag() -> None:
    os.environ["OTEL_EXPORTER_OTLP_ENDPOINT"] = "http://127.0.0.1:4318"
    os.environ["OTEL_SDK_DISABLED"] = "true"
    from prism_otel.setup import _enabled

    assert _enabled() is False
    os.environ.pop("OTEL_EXPORTER_OTLP_ENDPOINT", None)
    os.environ.pop("OTEL_SDK_DISABLED", None)


def test_ckv2_aws_57_no_longer_skipped() -> None:
    """Phase 6 deferred rotation; Phase 10 must close the loop, not re-defer."""
    skips = (ROOT / "infra/terraform/aws/.checkov.yml").read_text(encoding="utf-8")
    ledger = (ROOT / "infra/terraform/aws/CHECKOV_SKIPS.md").read_text(encoding="utf-8")
    secrets = (ROOT / "infra/terraform/aws/modules/secrets/main.tf").read_text(encoding="utf-8")
    rotation = (ROOT / "infra/terraform/aws/modules/secrets/rotation.tf").read_text(
        encoding="utf-8"
    )

    assert "CKV2_AWS_57" not in skips
    assert "CKV2_AWS_57" in ledger  # mentioned as closed
    assert "Closed in Phase 10" in ledger
    assert "#checkov:skip=CKV2_AWS_57" not in secrets
    assert "aws_secretsmanager_secret_rotation" in rotation


def test_per_service_dashboards_and_waf_owasp_additions() -> None:
    obs = (ROOT / "infra/terraform/aws/modules/observability/main.tf").read_text(encoding="utf-8")
    waf = (ROOT / "infra/terraform/aws/modules/alb_waf/main.tf").read_text(encoding="utf-8")
    assert 'aws_cloudwatch_dashboard" "service"' in obs
    assert "service_cpu" in obs and "service_latency" in obs and "service_5xx" in obs
    assert "AWSManagedRulesSQLiRuleSet" in waf
    assert "AWSManagedRulesAmazonIpReputationList" in waf


def test_phase10_security_docs_exist() -> None:
    required = [
        "docs/security/iam-least-privilege-audit.md",
        "docs/security/waf-owasp-top10-review.md",
        "docs/runbooks/secrets-rotation.md",
        "observability/collector/otel-collector-config.yaml",
        "observability/load-tests/run_load_test.py",
        "observability/otel/src/prism_otel/setup.py",
        "PHASE_10_COMPLETION.md",
    ]
    missing = [p for p in required if not (ROOT / p).is_file()]
    assert missing == [], f"Missing Phase 10 artifacts: {missing}"


def test_ecs_bound_services_call_prism_otel() -> None:
    samples = {
        "activation-gateway/src/prism_activation_gateway/api.py": "instrument_fastapi",
        "cv-service/src/prism_cv_service/api.py": "instrument_fastapi",
        "ai-copilot/src/prism_ai_copilot/api.py": "instrument_fastapi",
        "control-plane/fleet/apps.py": "prism_control.otel",
        "ingestion/src/prism_ingestion/__main__.py": "setup_tracing",
    }
    for path, needle in samples.items():
        text = (ROOT / path).read_text(encoding="utf-8")
        assert needle in text, f"{path} missing {needle}"
