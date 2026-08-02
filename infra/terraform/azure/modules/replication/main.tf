# Lakehouse mirror job definition (warm standby).
# The Databricks Jobs API object is rendered as JSON for human apply / workspace import.
# We intentionally do NOT use the databricks Terraform provider here — that provider
# requires a live workspace host + token, which violates ADR-001 validate-only CI.
terraform {
  required_version = ">= 1.5.0"
}

variable "name_prefix" { type = string }
variable "aws_gold_bucket" { type = string }
variable "aws_raw_bucket" { type = string }
variable "adls_gold_abfss" { type = string }
variable "storage_account_name" { type = string }
variable "schedule_cron_utc" { type = string }
variable "rpo_minutes" { type = number }
variable "rto_hours" { type = number }
variable "databricks_workspace_url" { type = string }

locals {
  job_name = "${var.name_prefix}-lakehouse-mirror"

  job_definition = {
    name = local.job_name
    tags = {
      project = "prism"
      phase   = "7"
      role    = "azure-dr-replication"
      rpo_min = tostring(var.rpo_minutes)
      rto_hr  = tostring(var.rto_hours)
    }
    schedule = {
      quartz_cron_expression = var.schedule_cron_utc
      timezone_id            = "UTC"
      pause_status           = "UNPAUSED"
    }
    max_concurrent_runs = 1
    timeout_seconds     = 3600
    tasks = [
      {
        task_key = "mirror_gold"
        notebook_task = {
          notebook_path = "/Repos/prism/azure_dr/mirror_lakehouse"
          base_parameters = {
            aws_gold_uri   = "s3a://${var.aws_gold_bucket}/lakehouse/gold/"
            aws_raw_uri    = "s3a://${var.aws_raw_bucket}/bronze/"
            adls_gold_uri  = var.adls_gold_abfss
            adls_bronze_uri = "abfss://bronze@${var.storage_account_name}.dfs.core.windows.net/"
            adls_silver_uri = "abfss://silver@${var.storage_account_name}.dfs.core.windows.net/"
            rpo_minutes    = tostring(var.rpo_minutes)
          }
        }
        new_cluster = {
          spark_version       = "14.3.x-scala2.12"
          node_type_id        = "Standard_DS3_v2"
          num_workers         = 2
          data_security_mode  = "SINGLE_USER"
          spark_conf = {
            "spark.databricks.delta.preview.enabled" = "true"
          }
          azure_attributes = {
            availability       = "SPOT_WITH_FALLBACK_AZURE"
            first_on_demand    = 1
            spot_bid_max_price = -1
          }
        }
      }
    ]
  }
}

output "job_name" { value = local.job_name }
output "job_definition_json" {
  description = "Databricks Jobs API payload — import at human apply time"
  value       = jsonencode(local.job_definition)
}
output "rpo_minutes" { value = var.rpo_minutes }
output "rto_hours" { value = var.rto_hours }
output "schedule_cron_utc" { value = var.schedule_cron_utc }
output "import_hint" {
  value = "After workspace exists: databricks jobs create --json @job.json against https://${var.databricks_workspace_url} (human only)."
}
