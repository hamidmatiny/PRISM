terraform {
  required_version = ">= 1.5.0"

  required_providers {
    # Phase 0 scaffold uses null only so `terraform validate` needs no cloud creds (ADR-001).
    # AWS provider + real modules land in Phase 6.
    null = {
      source  = "hashicorp/null"
      version = "~> 3.2"
    }
  }
}
