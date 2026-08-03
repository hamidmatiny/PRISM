# PRISM — local developer entrypoints
# ADR-001: no cloud apply targets here.

.PHONY: help setup up down logs test lint fmt terraform-validate terraform-aws-plan \
	checkov-aws checkov-azure tflint-aws tflint-azure export-schemas \
	lakehouse-run lakehouse-run-live dbt-build uc-validate \
	phase1-check phase2-check phase3-check phase4-check phase5-check \
	phase6-check phase7-check phase8-check phase9-check phase10-check \
	phase11-check phase12-check phase13-check phase14-check phase16-check \
	phase17-check phase18-check cockpit-build demo e2e

CHECKOV_VERSION := $(shell tr -d '[:space:]' < infra/terraform/CHECKOV_VERSION)

help:
	@echo "PRISM targets:"
	@echo "  make setup              - local (non-Docker) dev env: deps + editable installs"
	@echo "  make up                 - docker compose up (local, zero cloud creds)"
	@echo "  make down               - docker compose down"
	@echo "  make logs               - follow compose logs"
	@echo "  make test               - unit tests"
	@echo "  make lint               - ruff check + format check"
	@echo "  make fmt                - ruff format"
	@echo "  make export-schemas     - regenerate contract JSON Schema files"
	@echo "  make lakehouse-run      - Spark local medallion on fixtures"
	@echo "  make dbt-build          - dbt build + docs generate (DuckDB)"
	@echo "  make uc-validate        - structural UC bootstrap / Lakeflow checks"
	@echo "  make terraform-validate - validate aws + azure stacks (no apply)"
	@echo "  make terraform-aws-plan - mock-credential plan → tfplan.txt (no apply)"
	@echo "  make tflint-aws         - tflint on aws (same as CI)"
	@echo "  make tflint-azure       - tflint on azure (same as CI)"
	@echo "  make checkov-aws        - checkov on aws stack (same flags as CI)"
	@echo "  make checkov-azure      - checkov on azure stack (same flags as CI)"
	@echo "  make phase6-check       - lint + test + terraform-validate + checkov"
	@echo "  make phase7-check       - lint + test + validate + tflint + checkov (CI-parity)"
	@echo "  make cockpit-build      - npm ci + typecheck + build (same as CI cockpit job)"
	@echo "  make phase8-check       - lint + test + cockpit-build"
	@echo "  make phase9-check       - lint + test (includes copilot grounding)"
	@echo "  make phase10-check      - lint + test + terraform-validate + checkov-aws"
	@echo "  make demo               - full local demo stack + seed (<5 min)"
	@echo "  make e2e                - live golden-path (requires make demo)"
	@echo "  make phase11-check      - lint + unit tests + cockpit + terraform gates"
	@echo "  make phase12-check      - lint + unit tests (scenario-engine + ADR-005)"
	@echo "  make phase13-check      - lint + unit tests (two-layer validation hardening)"
	@echo "  make phase14-check      - lint + unit tests (per-source circuit breaker)"
	@echo "  make phase16-check      - lint + unit tests (drift-monitor, honest baseline)"
	@echo "  make phase17-check      - lint + unit tests (Dagster orchestration)"
	@echo "  make phase18-check      - lint + opa test + unit tests (Rego trip policies)"

setup:
	@echo "Installing dev/test deps (mirrors CI's test job exactly — see requirements-dev.txt)"
	python -m pip install --upgrade pip
	python -m pip install -r requirements-dev.txt
	python -m pip install -e contracts/telemetry-schema
	python -m pip install -e contracts/cv-finding-schema
	python -m pip install -e contracts/activation-contract
	python -m pip install -e ingestion
	python -m pip install -e scenario-engine
	python -m pip install -e incident-engine
	python -m pip install -e drift-monitor
	python -m pip install -e lakehouse
	python -m pip install -e orchestration
	python -m pip install -e cv-service
	python -m pip install -e activation-gateway
	python -m pip install -e control-plane
	python -m pip install -e ai-copilot
	python -m pip install -e observability/otel
	@echo ""
	@echo "Done. Java 17 is a separate, manual prerequisite for the one Spark-backed"
	@echo "unit test (test_medallion_local_spark) -- see README 'Local (non-Docker)"
	@echo "test setup'. Everything else in \"make test\" runs without it."

up:
	docker compose up -d --build

demo:
	bash examples/demo/run_demo.sh

e2e:
	PRISM_E2E=1 pytest -q tests/e2e

down:
	docker compose down

logs:
	docker compose logs -f

test:
	pytest -q tests/unit

lint:
	ruff check .
	ruff format --check .

fmt:
	ruff format .

export-schemas:
	python -m prism_telemetry_schema.export
	python -m prism_cv_finding_schema.export

lakehouse-run:
	@echo "NOTE: fixture bronze (CI). For live ingest bronze use: docker compose --profile lakehouse run --rm lakehouse"
	python -m prism_lakehouse \
		--bronze-root lakehouse/fixtures/bronze \
		--warehouse-root .data/lakehouse-from-fixtures

lakehouse-run-live:
	docker compose --profile lakehouse run --rm lakehouse

dbt-build:
	cd dbt && DBT_PROFILES_DIR=$$PWD dbt build --target duckdb
	cd dbt && DBT_PROFILES_DIR=$$PWD dbt docs generate --target duckdb

uc-validate:
	python lakehouse/unity_catalog/render_bootstrap.py --check
	python lakehouse/unity_catalog/validate_bootstrap.py

terraform-validate:
	cd infra/terraform/aws && terraform init -backend=false -input=false && terraform validate
	cd infra/terraform/azure && terraform init -backend=false -input=false && terraform validate

# ADR-001: mock credentials only. Never export real AWS keys into this target.
terraform-aws-plan:
	cd infra/terraform/aws && terraform init -input=false -reconfigure
	cd infra/terraform/aws && \
		AWS_ACCESS_KEY_ID=AKIAIOSFODNN7EXAMPLE \
		AWS_SECRET_ACCESS_KEY=wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY \
		AWS_EC2_METADATA_DISABLED=true \
		AWS_REGION=us-east-1 \
		terraform plan -input=false -lock=false -no-color -out=tfplan.binary | tee tfplan.txt
	cd infra/terraform/aws && terraform show -no-color tfplan.binary >> tfplan.txt

# Identical tflint invocation to .github/workflows/ci.yml
tflint-aws:
	cd infra/terraform/aws && tflint --init && tflint --format compact

tflint-azure:
	cd infra/terraform/azure && tflint --init && tflint --format compact

# Identical checkov invocation to .github/workflows/ci.yml (no CLI --skip-check).
checkov-aws:
	@command -v checkov >/dev/null || pip install "checkov==$(CHECKOV_VERSION)"
	checkov -d infra/terraform/aws \
		--config-file infra/terraform/aws/.checkov.yml \
		--framework terraform \
		--compact --quiet

checkov-azure:
	@command -v checkov >/dev/null || pip install "checkov==$(CHECKOV_VERSION)"
	checkov -d infra/terraform/azure \
		--config-file infra/terraform/azure/.checkov.yml \
		--framework terraform \
		--compact --quiet

phase0-check: lint test terraform-validate

phase1-check: lint test terraform-validate

phase2-check: lint test uc-validate terraform-validate

phase3-check: lint test uc-validate terraform-validate

phase4-check: lint test uc-validate terraform-validate

phase5-check: lint test uc-validate terraform-validate

phase6-check: lint test terraform-validate checkov-aws checkov-azure

# Full local gate matching CI lint + test + terraform matrix (validate/tflint/checkov).
phase7-check: lint test terraform-validate tflint-aws tflint-azure checkov-aws checkov-azure

cockpit-build:
	cd cockpit && npm ci && npm run typecheck && npm run build && node --test src/lib/token.test.mjs

phase8-check: lint test cockpit-build

phase9-check: lint test

phase10-check: lint test terraform-validate checkov-aws

# Prior-phase gates simultaneously (e2e is live — run `make demo && make e2e` separately).
phase11-check: lint test cockpit-build terraform-validate tflint-aws tflint-azure checkov-aws checkov-azure

phase12-check: lint test

phase13-check: lint test

phase14-check: lint test

phase16-check: lint test

phase17-check: lint test

phase18-check: lint
	opa test incident-engine/policies/rego -v
	$(MAKE) test
