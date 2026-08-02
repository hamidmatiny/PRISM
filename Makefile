# PRISM — local developer entrypoints
# ADR-001: no cloud apply targets here.

.PHONY: help up down logs test lint fmt terraform-validate export-schemas phase0-check phase1-check

help:
	@echo "PRISM targets:"
	@echo "  make up                 - docker compose up (local, zero cloud creds)"
	@echo "  make down               - docker compose down"
	@echo "  make logs               - follow compose logs"
	@echo "  make test               - unit tests"
	@echo "  make lint               - ruff check + format check"
	@echo "  make fmt                - ruff format"
	@echo "  make export-schemas     - regenerate contract JSON Schema files"
	@echo "  make terraform-validate - validate aws + azure stacks (no apply)"
	@echo "  make phase1-check       - lint + test + terraform-validate"

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

terraform-validate:
	cd infra/terraform/aws && terraform init -backend=false -input=false && terraform validate
	cd infra/terraform/azure && terraform init -backend=false -input=false && terraform validate

phase0-check: lint test terraform-validate

phase1-check: lint test terraform-validate
