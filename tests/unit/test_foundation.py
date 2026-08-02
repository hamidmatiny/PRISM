"""Phase 0 foundation checks — monorepo layout and contract stubs."""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]

REQUIRED_TOP_LEVEL = [
    ".cursor/rules",
    ".github/workflows",
    "contracts",
    "ingestion",
    "cv-service",
    "lakehouse",
    "dbt",
    "activation-gateway",
    "control-plane",
    "ai-copilot",
    "cockpit",
    "infra/terraform/aws",
    "infra/terraform/azure",
    "observability",
    "docs/adr",
    "docs/runbooks",
    "examples",
    "tests/e2e",
]

REQUIRED_FILES = [
    "README.md",
    "ARCHITECTURE.md",
    "PHASE_0_COMPLETION.md",
    "PHASE_1_COMPLETION.md",
    "PHASE_2_COMPLETION.md",
    "PHASE_3_COMPLETION.md",
    "PHASE_4_COMPLETION.md",
    "PHASE_5_COMPLETION.md",
    "docker-compose.yml",
    "Makefile",
    ".env.example",
    "docs/adr/001-cost-safety-policy.md",
    "docs/adr/002-multi-warehouse-activation.md",
    ".cursor/rules/cost-safety.mdc",
    ".cursor/rules/contract-first.mdc",
    ".cursor/rules/monorepo.mdc",
    ".github/workflows/ci.yml",
    "contracts/telemetry-schema/README.md",
    "contracts/telemetry-schema/schemas/sensor_ping.schema.json",
    "contracts/cv-finding-schema/README.md",
    "contracts/cv-finding-schema/schemas/cv_finding.schema.json",
    "contracts/activation-contract/openapi.yaml",
    "contracts/activation-contract/src/prism_activation_contract/models.py",
    "ingestion/Dockerfile",
    "lakehouse/Dockerfile",
    "lakehouse/quality/expectations.yaml",
    "lakehouse/unity_catalog/bootstrap.sql",
    "dbt/dbt_project.yml",
    "dbt/docs/dbt-cloud-path.md",
    "cv-service/Dockerfile",
    "cv-service/models/yolo_fleet_defects_tiny.onnx",
    "cv-service/docs/LABELS.md",
    "activation-gateway/Dockerfile",
    "activation-gateway/fixtures/gold/asset_daily_metrics/part-000.parquet",
    "tests/unit/test_activation_conformance.py",
    "control-plane/Dockerfile",
    "control-plane/docs/ASYNC_TASKS.md",
    "docs/RELEASE_PLAN.md",
    "docs/PACKAGING_PLAN.md",
    "CHANGELOG.md",
]


def test_required_directories_exist() -> None:
    missing = [p for p in REQUIRED_TOP_LEVEL if not (ROOT / p).exists()]
    assert missing == [], f"Missing directories: {missing}"


def test_required_files_exist() -> None:
    missing = [p for p in REQUIRED_FILES if not (ROOT / p).is_file()]
    assert missing == [], f"Missing files: {missing}"


def test_every_top_level_component_has_readme() -> None:
    components = [
        "contracts",
        "ingestion",
        "cv-service",
        "lakehouse",
        "dbt",
        "activation-gateway",
        "control-plane",
        "ai-copilot",
        "cockpit",
        "infra",
        "observability",
        "examples",
    ]
    missing = [c for c in components if not (ROOT / c / "README.md").is_file()]
    assert missing == [], f"Components missing README.md: {missing}"


def test_adr001_mentions_no_terraform_apply_in_ci() -> None:
    text = (ROOT / "docs/adr/001-cost-safety-policy.md").read_text(encoding="utf-8")
    assert "terraform apply" in text.lower()
    assert "duckdb" in text.lower()
    assert "localstack" in text.lower()
