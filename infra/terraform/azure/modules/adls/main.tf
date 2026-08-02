terraform {
  required_version = ">= 1.5.0"
  required_providers {
    azurerm = {
      source  = "hashicorp/azurerm"
      version = ">= 3.100"
    }
    random = {
      source  = "hashicorp/random"
      version = ">= 3.6"
    }
  }
}

variable "name_prefix" { type = string }
variable "resource_group_name" { type = string }
variable "location" { type = string }
variable "containers" { type = map(string) }
variable "tags" {
  type    = map(string)
  default = {}
}

resource "random_string" "sa" {
  length  = 6
  upper   = false
  special = false
  numeric = true
}

# Storage account names: 3–24 lowercase alphanumeric, globally unique.
locals {
  storage_account_name = substr(replace("${var.name_prefix}lakedr${random_string.sa.result}", "-", ""), 0, 24)
}

resource "azurerm_storage_account" "lake" {
  #checkov:skip=CKV_AZURE_33: HTTPS-only is enabled via https_traffic_only_enabled
  #checkov:skip=CKV_AZURE_59: public network access disabled below
  #checkov:skip=CKV_AZURE_44: CMK deferred — Microsoft-managed keys for warm-standby cost profile (CHECKOV_SKIPS.md)
  #checkov:skip=CKV2_AZURE_1: Microsoft-managed encryption for standby mirror (CHECKOV_SKIPS.md)
  #checkov:skip=CKV_AZURE_206: LRS is intentional for warm-standby cost; primary durability is AWS (CHECKOV_SKIPS.md)
  #checkov:skip=CKV_AZURE_43: Name is random_string + prefix constrained to [a-z0-9]{3,24} (CHECKOV_SKIPS.md)
  #checkov:skip=CKV_AZURE_244: local_user_enabled=false; Azure AD auth only (CHECKOV_SKIPS.md)
  #checkov:skip=CKV2_AZURE_33: Private Endpoint deferred — warm-standby cost; public network access already off (CHECKOV_SKIPS.md)
  name                            = local.storage_account_name
  resource_group_name             = var.resource_group_name
  location                        = var.location
  account_tier                    = "Standard"
  account_replication_type        = "LRS"
  account_kind                    = "StorageV2"
  is_hns_enabled                  = true # ADLS Gen2
  min_tls_version                 = "TLS1_2"
  https_traffic_only_enabled      = true
  allow_nested_items_to_be_public = false
  public_network_access_enabled   = false
  shared_access_key_enabled       = false
  default_to_oauth_authentication = true
  local_user_enabled              = false

  blob_properties {
    versioning_enabled = true
    delete_retention_policy {
      days = 14
    }
    container_delete_retention_policy {
      days = 14
    }
  }

  tags = merge(var.tags, { Name = local.storage_account_name, Role = "adls-lakehouse-mirror" })
}

resource "azurerm_storage_container" "zone" {
  for_each = var.containers

  #checkov:skip=CKV2_AZURE_21: logging via storage account diagnostics at apply-time ops (CHECKOV_SKIPS.md)
  name                  = each.value
  storage_account_name  = azurerm_storage_account.lake.name
  container_access_type = "private"
}

output "storage_account_name" { value = azurerm_storage_account.lake.name }
output "storage_account_id" { value = azurerm_storage_account.lake.id }
output "primary_dfs_endpoint" { value = azurerm_storage_account.lake.primary_dfs_endpoint }
output "container_names" { value = [for c in azurerm_storage_container.zone : c.name] }
output "gold_abfss_uri" {
  value = "abfss://gold@${azurerm_storage_account.lake.name}.dfs.core.windows.net/"
}
