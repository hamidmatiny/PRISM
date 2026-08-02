# ADR-001: validate / tflint / checkov only in CI. Never apply from automation.
# No azurerm data sources that call live Azure APIs (keeps validate offline).
provider "azurerm" {
  features {
    resource_group {
      prevent_deletion_if_contains_resources = true
    }
  }

  # Set at human apply time. Placeholders keep validate/plan graph offline-friendly.
  subscription_id            = var.azure_subscription_id
  tenant_id                  = var.azure_tenant_id
  skip_provider_registration = true

  # CI / local structural checks never present real service principals.
  # Humans authenticate via az login or ARM_* env before apply.
  storage_use_azuread = true
}

provider "random" {}
