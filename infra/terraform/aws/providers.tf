# ADR-001: CI plans with mock credentials + skips. Never apply from automation.
provider "aws" {
  region = var.aws_region

  # Allow validate/plan without real AWS credentials (CI artifact path).
  # Humans remove these skips (or override via env) before a real apply.
  skip_credentials_validation = var.aws_skip_credentials_validation
  skip_requesting_account_id  = var.aws_skip_requesting_account_id
  skip_metadata_api_check     = true
  skip_region_validation      = true

  default_tags {
    tags = local.common_tags
  }
}

provider "random" {}
