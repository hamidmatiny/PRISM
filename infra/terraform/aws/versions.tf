terraform {
  required_version = ">= 1.5.0"

  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.70"
    }
    random = {
      source  = "hashicorp/random"
      version = "~> 3.6"
    }
  }

  # Local backend for validate/plan in CI (ADR-001). Remote backend is a
  # human-owned apply-time concern — never configured for automated apply.
  backend "local" {
    path = "terraform.tfstate"
  }
}
