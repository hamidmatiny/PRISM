output "phase" {
  description = "Platform phase marker"
  value       = "7"
}

output "resource_group_name" {
  description = "Azure DR resource group"
  value       = module.resource_group.name
}

output "storage_account_name" {
  description = "ADLS Gen2 storage account (lakehouse mirror)"
  value       = module.adls.storage_account_name
}

output "gold_abfss_uri" {
  description = "abfss URI for mirrored gold — activation-gateway failover target"
  value       = module.adls.gold_abfss_uri
}

output "databricks_workspace_url" {
  description = "Azure Databricks workspace URL (warm standby)"
  value       = module.databricks.workspace_url
}

output "replication_job_name" {
  description = "Databricks job name for S3→ADLS mirror"
  value       = module.replication.job_name
}

output "replication_job_definition_json" {
  description = "Jobs API JSON for human import after workspace apply"
  value       = module.replication.job_definition_json
  sensitive   = false
}

output "rpo_minutes" {
  description = "Recovery Point Objective (minutes) — bound to replication cron"
  value       = module.replication.rpo_minutes
}

output "rto_hours" {
  description = "Recovery Time Objective (hours) — manual failover runbook bound"
  value       = module.replication.rto_hours
}

output "rpo_rto" {
  description = "RPO/RTO summary object"
  value       = local.rpo_rto
}

output "failover_runbook" {
  description = "How to repoint activation-gateway at the Azure mirror"
  value       = "docs/runbooks/azure-dr-failover.md"
}

output "apply_warning" {
  description = "Reminder — never apply from CI/agents (ADR-001)"
  value       = "Human-gated terraform apply only. CI is validate/tflint/checkov."
}
