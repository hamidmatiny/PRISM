# PRISM Azure DR root — Phase 7.
# Warm-standby Databricks + ADLS Gen2 mirror of the AWS lakehouse.
# ADR-001: validate / tflint / checkov only in CI. Humans apply out-of-band.

module "resource_group" {
  source = "./modules/resource_group"

  name     = "${local.name_prefix}-dr-rg"
  location = var.location
  tags     = local.common_tags
}

module "adls" {
  source = "./modules/adls"

  name_prefix         = local.name_prefix
  resource_group_name = module.resource_group.name
  location            = module.resource_group.location
  containers          = local.lakehouse_containers
  tags                = local.common_tags
}

module "databricks" {
  source = "./modules/databricks"

  name_prefix         = local.name_prefix
  resource_group_name = module.resource_group.name
  location            = module.resource_group.location
  sku                 = var.databricks_sku
  tags                = local.common_tags
}

module "replication" {
  source = "./modules/replication"

  name_prefix              = local.name_prefix
  aws_gold_bucket          = var.aws_gold_bucket
  aws_raw_bucket           = var.aws_raw_bucket
  adls_gold_abfss          = module.adls.gold_abfss_uri
  storage_account_name     = module.adls.storage_account_name
  schedule_cron_utc        = var.replication_schedule_cron
  rpo_minutes              = var.rpo_minutes
  rto_hours                = var.rto_hours
  databricks_workspace_url = module.databricks.workspace_url
}
