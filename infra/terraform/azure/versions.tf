terraform {
  required_version = ">= 1.5.0"

  required_providers {
    azurerm = {
      source  = "hashicorp/azurerm"
      version = "~> 3.116"
    }
    random = {
      source  = "hashicorp/random"
      version = "~> 3.6"
    }
  }

  # Local backend for validate in CI (ADR-001). Remote backend is human apply-time only.
  backend "local" {
    path = "terraform.tfstate"
  }
}
