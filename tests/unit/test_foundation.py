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
    "PHASE_6_COMPLETION.md",
    "PHASE_7_COMPLETION.md",
    "PHASE_8_COMPLETION.md",
    "PHASE_9_COMPLETION.md",
    "PHASE_10_COMPLETION.md",
    "PHASE_11_COMPLETION.md",
    "docs/DEMO_SCRIPT.md",
    "docs/adr/index.md",
    "docs/adr/004-copilot-non-fabrication.md",
    "docs/runbooks/README.md",
    "docs/README.md",
    "examples/demo/run_demo.sh",
    "examples/demo/seed.py",
    "tests/e2e/test_golden_path.py",
    "docker-compose.demo.yml",
    "docs/security/iam-least-privilege-audit.md",
    "docs/security/waf-owasp-top10-review.md",
    "docs/runbooks/secrets-rotation.md",
    "observability/otel/pyproject.toml",
    "observability/collector/otel-collector-config.yaml",
    "observability/load-tests/run_load_test.py",
    "infra/terraform/aws/modules/secrets/rotation.tf",
    "ai-copilot/pyproject.toml",
    "ai-copilot/Dockerfile",
    "ai-copilot/README.md",
    "docker-compose.yml",
    "cockpit/package.json",
    "cockpit/src/main.ts",
    "cockpit/src/styles/tokens.css",
    "cockpit/README.md",
    "Makefile",
    ".env.example",
    "docs/adr/001-cost-safety-policy.md",
    "docs/adr/002-multi-warehouse-activation.md",
    "docs/adr/003-azure-dr-two-cloud-tradeoff.md",
    "docs/runbooks/azure-dr-failover.md",
    ".cursor/rules/cost-safety.mdc",
    ".cursor/rules/contract-first.mdc",
    ".cursor/rules/monorepo.mdc",
    ".github/workflows/ci.yml",
    "infra/terraform/aws/main.tf",
    "infra/terraform/aws/modules/vpc/main.tf",
    "infra/terraform/aws/modules/ecs/main.tf",
    "infra/terraform/aws/modules/iam/main.tf",
    "infra/terraform/aws/modules/rds/main.tf",
    "infra/terraform/aws/modules/alb_waf/main.tf",
    "infra/terraform/aws/modules/s3/main.tf",
    "infra/terraform/aws/modules/secrets/main.tf",
    "infra/terraform/aws/modules/kms/main.tf",
    "infra/terraform/aws/modules/observability/main.tf",
    "infra/terraform/aws/.checkov.yml",
    "infra/terraform/aws/CHECKOV_SKIPS.md",
    "infra/terraform/CHECKOV_VERSION",
    "infra/terraform/aws/.tflint.hcl",
    "infra/terraform/azure/main.tf",
    "infra/terraform/azure/modules/adls/main.tf",
    "infra/terraform/azure/modules/databricks/main.tf",
    "infra/terraform/azure/modules/replication/main.tf",
    "infra/terraform/azure/modules/resource_group/main.tf",
    "infra/terraform/azure/.checkov.yml",
    "infra/terraform/azure/CHECKOV_SKIPS.md",
    "infra/terraform/azure/README.md",
    "infra/terraform/azure/.tflint.hcl",
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


def test_ci_checkov_does_not_override_yaml_skips() -> None:
    """CLI --skip-check replaces .checkov.yml skip-check (checkov precedence).

    Phase 6 CI failed because workflows/ci.yml passed skip_check: CKV_TF_1 while
    also setting config_file — wiping the documented skip list. Guard that gap.
    """
    ci = (ROOT / ".github/workflows/ci.yml").read_text(encoding="utf-8")
    assert "--config-file" in ci
    assert "skip_check:" not in ci
    # Comments may mention the flag; executable lines must not pass it.
    executable = "\n".join(
        ln for ln in ci.splitlines() if ln.strip() and not ln.strip().startswith("#")
    )
    assert "--skip-check" not in executable


def test_makefile_checkov_matches_ci_flags() -> None:
    makefile = (ROOT / "Makefile").read_text(encoding="utf-8")
    assert "--config-file infra/terraform/aws/.checkov.yml" in makefile
    assert "--config-file infra/terraform/azure/.checkov.yml" in makefile
    assert "--framework terraform" in makefile
    assert "--compact" in makefile and "--quiet" in makefile
    assert "phase7-check:" in makefile
    assert "tflint-azure:" in makefile


def test_azure_readme_has_test_it_yourself() -> None:
    text = (ROOT / "infra/terraform/azure/README.md").read_text(encoding="utf-8")
    assert "Test it yourself" in text
    assert "make phase7-check" in text
    assert "terraform validate" in text


def test_adr003_and_failover_runbook_are_real() -> None:
    adr = ROOT / "docs/adr/003-azure-dr-two-cloud-tradeoff.md"
    runbook = ROOT / "docs/runbooks/azure-dr-failover.md"
    index = (ROOT / "docs/adr/index.md").read_text(encoding="utf-8")
    rb_index = (ROOT / "docs/runbooks/README.md").read_text(encoding="utf-8")
    assert adr.is_file() and adr.stat().st_size > 500
    assert runbook.is_file() and runbook.stat().st_size > 500
    assert "003-azure-dr-two-cloud-tradeoff.md" in index
    assert "azure-dr-failover.md" in rb_index
    assert "marginal" in adr.read_text(encoding="utf-8").lower()
    assert "PRISM_ACTIVATION_GOLD_ROOT" in runbook.read_text(encoding="utf-8")


def test_adr_index_lists_every_adr_file() -> None:
    """Index files must not lag behind content (regression for ADR-003/004)."""
    adr_dir = ROOT / "docs/adr"
    index = (adr_dir / "index.md").read_text(encoding="utf-8")
    adr_files = sorted(p.name for p in adr_dir.glob("[0-9][0-9][0-9]-*.md"))
    assert adr_files == [
        "001-cost-safety-policy.md",
        "002-multi-warehouse-activation.md",
        "003-azure-dr-two-cloud-tradeoff.md",
        "004-copilot-non-fabrication.md",
    ], f"Unexpected ADR set: {adr_files}"
    missing = [name for name in adr_files if name not in index]
    assert missing == [], f"docs/adr/index.md missing rows for: {missing}"


def test_runbooks_index_lists_written_runbooks() -> None:
    rb_dir = ROOT / "docs/runbooks"
    index = (rb_dir / "README.md").read_text(encoding="utf-8")
    for name in ("azure-dr-failover.md", "secrets-rotation.md"):
        assert (rb_dir / name).is_file()
        assert name in index, f"docs/runbooks/README.md missing {name}"
    assert "Pending" not in index
