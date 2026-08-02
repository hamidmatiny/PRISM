terraform {
  required_version = ">= 1.5.0"
  required_providers {
    azurerm = {
      source  = "hashicorp/azurerm"
      version = ">= 3.100"
    }
  }
}

variable "name_prefix" { type = string }
variable "resource_group_name" { type = string }
variable "location" { type = string }
variable "sku" { type = string }
variable "tags" {
  type    = map(string)
  default = {}
}

resource "azurerm_databricks_workspace" "dr" {
  #checkov:skip=CKV_AZURE_158: Public network access retained for warm-standby job ingress; private link is prod harden (CHECKOV_SKIPS.md)
  name                        = "${var.name_prefix}-dbw-dr"
  resource_group_name         = var.resource_group_name
  location                    = var.location
  sku                         = var.sku
  managed_resource_group_name = "${var.name_prefix}-dbw-dr-managed"
  tags                        = merge(var.tags, { Name = "${var.name_prefix}-dbw-dr" })

  custom_parameters {
    no_public_ip = true
  }
}

output "workspace_id" { value = azurerm_databricks_workspace.dr.id }
output "workspace_url" { value = azurerm_databricks_workspace.dr.workspace_url }
output "workspace_name" { value = azurerm_databricks_workspace.dr.name }
