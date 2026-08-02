terraform {
  required_version = ">= 1.5.0"
  required_providers {
    azurerm = {
      source  = "hashicorp/azurerm"
      version = ">= 3.100"
    }
  }
}

variable "name" { type = string }
variable "location" { type = string }
variable "tags" {
  type    = map(string)
  default = {}
}

resource "azurerm_resource_group" "this" {
  name     = var.name
  location = var.location
  tags     = var.tags
}

output "name" { value = azurerm_resource_group.this.name }
output "location" { value = azurerm_resource_group.this.location }
output "id" { value = azurerm_resource_group.this.id }
