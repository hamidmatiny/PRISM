# PRISM — local developer entrypoints
# ADR-001: no cloud apply targets here.

.PHONY: help up down logs test lint fmt terraform-validate export-schemas \
	lakehouse-run dbt-build uc-validate phase1-check phase2-check

help:
	@echo "PRISM targets:"
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
	@echo "  make phase2-check       - lint + test + uc-validate + terraform-validate"

up:
	docker compose up -d --build

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
	python -m prism_lakehouse \
		--bronze-root lakehouse/fixtures/bronze \
		--warehouse-root .data/lakehouse

dbt-build:
	cd dbt && DBT_PROFILES_DIR=$$PWD dbt build --target duckdb
	cd dbt && DBT_PROFILES_DIR=$$PWD dbt docs generate --target duckdb

uc-validate:
	python lakehouse/unity_catalog/render_bootstrap.py --check
	python lakehouse/unity_catalog/validate_bootstrap.py

terraform-validate:
	cd infra/terraform/aws && terraform init -backend=false -input=false && terraform validate
	cd infra/terraform/azure && terraform init -backend=false -input=false && terraform validate

phase0-check: lint test terraform-validate

phase1-check: lint test terraform-validate

phase2-check: lint test uc-validate terraform-validate
