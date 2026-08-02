variable "project" {
  type        = string
  description = "Project name prefix"
  default     = "prism"
}

variable "environment" {
  type        = string
  description = "Environment name (dev / staging / prod)"
  default     = "dev"

  validation {
    condition     = contains(["dev", "staging", "prod"], var.environment)
    error_message = "environment must be one of: dev, staging, prod."
  }
}

variable "location" {
  type        = string
  description = "Azure region for the warm-standby DR footprint"
  default     = "eastus"
}

variable "azure_subscription_id" {
  type        = string
  description = "Azure subscription ID (placeholder OK for validate; real value at apply)"
  default     = "00000000-0000-0000-0000-000000000000"
}

variable "azure_tenant_id" {
  type        = string
  description = "Azure tenant ID (placeholder OK for validate; real value at apply)"
  default     = "00000000-0000-0000-0000-000000000000"
}

variable "aws_gold_bucket" {
  type        = string
  description = "Source AWS S3 gold bucket name mirrored into ADLS (no live lookup)"
  default     = "prism-dev-gold"
}

variable "aws_raw_bucket" {
  type        = string
  description = "Source AWS S3 raw bucket name (optional bronze mirror)"
  default     = "prism-dev-raw"
}

variable "replication_schedule_cron" {
  type        = string
  description = "Databricks job quartz cron (UTC) for lakehouse mirror — drives RPO"
  # Every 15 minutes → RPO target 15m (see locals / CHECKOV_SKIPS / ADR-003).
  default     = "0 */15 * * * ?"
}

variable "rpo_minutes" {
  type        = number
  description = "Recovery Point Objective in minutes (must match replication cadence)"
  default     = 15

  validation {
    condition     = var.rpo_minutes >= 5 && var.rpo_minutes <= 1440
    error_message = "rpo_minutes must be between 5 and 1440."
  }
}

variable "rto_hours" {
  type        = number
  description = "Recovery Time Objective in hours (manual failover runbook bound)"
  default     = 4

  validation {
    condition     = var.rto_hours >= 1 && var.rto_hours <= 72
    error_message = "rto_hours must be between 1 and 72."
  }
}

variable "databricks_sku" {
  type        = string
  description = "Azure Databricks workspace SKU (standard = warm standby cost profile)"
  default     = "standard"

  validation {
    condition     = contains(["standard", "premium"], var.databricks_sku)
    error_message = "databricks_sku must be standard or premium."
  }
}
