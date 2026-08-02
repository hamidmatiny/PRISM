# PRISM — local developer entrypoints
# ADR-001: no cloud apply targets here.

.PHONY: help up down logs test lint fmt terraform-validate phase0-check

help:
	@echo "PRISM targets:"
	@echo "  make up                 - docker compose up (local, zero cloud creds)"
	@echo "  make down               - docker compose down"
	@echo "  make logs               - follow compose logs"
	@echo "  make test               - unit tests"
	@echo "  make lint               - ruff check + format check"
	@echo "  make fmt                - ruff format"
	@echo "  make terraform-validate - validate aws + azure stacks (no apply)"
	@echo "  make phase0-check       - lint + test + terraform-validate"

up:
	docker compose up -d

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

terraform-validate:
	cd infra/terraform/aws && terraform init -backend=false -input=false && terraform validate
	cd infra/terraform/azure && terraform init -backend=false -input=false && terraform validate

phase0-check: lint test terraform-validate
