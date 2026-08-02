# PRISM — local developer entrypoints
# ADR-001: no cloud apply targets here.

.PHONY: help up down logs test lint fmt terraform-validate terraform-aws-plan \
	export-schemas lakehouse-run lakehouse-run-live dbt-build uc-validate \
	phase1-check phase2-check phase3-check phase4-check phase5-check phase6-check

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
	@echo "  make terraform-aws-plan - mock-credential plan → tfplan.txt (no apply)"
	@echo "  make phase2-check       - lint + test + uc-validate + terraform-validate"
	@echo "  make phase3-check       - lint + test + uc-validate + terraform-validate"
	@echo "  make phase4-check       - lint + test + uc-validate + terraform-validate"
	@echo "  make phase5-check       - lint + test + uc-validate + terraform-validate"
	@echo "  make phase6-check       - lint + test + terraform-validate (+ local plan optional)"

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

phase0-check: lint test terraform-validate

phase1-check: lint test terraform-validate

phase2-check: lint test uc-validate terraform-validate

phase3-check: lint test uc-validate terraform-validate

phase4-check: lint test uc-validate terraform-validate

phase5-check: lint test uc-validate terraform-validate

phase6-check: lint test terraform-validate
