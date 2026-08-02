# PRISM AWS platform root — Phase 6.
# ADR-001: validate / tflint / checkov / plan only in CI. Humans apply out-of-band.

module "kms" {
  source = "./modules/kms"

  name_prefix    = local.name_prefix
  aws_account_id = var.aws_account_id
  aws_region     = var.aws_region
  tags           = local.common_tags
}

module "vpc" {
  source = "./modules/vpc"

  name_prefix        = local.name_prefix
  cidr               = var.vpc_cidr
  aws_region         = var.aws_region
  availability_zones = var.availability_zones
  kms_key_arn        = module.kms.key_arn
  tags               = local.common_tags
}

module "s3" {
  source = "./modules/s3"

  name_prefix                 = local.name_prefix
  raw_glacier_transition_days = var.raw_glacier_transition_days
  kms_key_arn                 = module.kms.key_arn
  aws_account_id              = var.aws_account_id
  elb_account_id              = var.elb_account_id
  tags                        = local.common_tags
}

module "secrets" {
  source = "./modules/secrets"

  name_prefix = local.name_prefix
  kms_key_arn = module.kms.key_arn
  tags        = local.common_tags
}

module "iam" {
  source = "./modules/iam"

  name_prefix     = local.name_prefix
  aws_region      = var.aws_region
  aws_account_id  = var.aws_account_id
  raw_bucket_arn  = module.s3.raw_bucket_arn
  gold_bucket_arn = module.s3.gold_bucket_arn
  rds_secret_arn  = module.secrets.rds_secret_arn
  app_secret_arn  = module.secrets.app_secret_arn
  kms_key_arn     = module.kms.key_arn
  tags            = local.common_tags
}

module "rds" {
  source = "./modules/rds"

  name_prefix                    = local.name_prefix
  vpc_id                         = module.vpc.vpc_id
  vpc_cidr                       = module.vpc.vpc_cidr
  isolated_subnet_ids            = module.vpc.isolated_subnet_ids
  private_subnet_cidrs_sg_source = module.vpc.vpc_cidr
  master_username                = module.secrets.rds_username
  master_password                = module.secrets.rds_password
  deletion_protection            = var.enable_deletion_protection
  kms_key_arn                    = module.kms.key_arn
  tags                           = local.common_tags
}

module "alb_waf" {
  source = "./modules/alb_waf"

  name_prefix           = local.name_prefix
  vpc_id                = module.vpc.vpc_id
  public_subnet_ids     = module.vpc.public_subnet_ids
  services              = { for k, v in local.services : k => { port = v.port, path_patterns = v.path_patterns, health_check_path = v.health_check_path } }
  certificate_arn       = var.alb_certificate_arn
  deletion_protection   = var.enable_deletion_protection
  access_logs_bucket_id = module.s3.logs_bucket_id
  kms_key_arn           = module.kms.key_arn
  tags                  = local.common_tags
}

module "ecs" {
  source = "./modules/ecs"

  name_prefix           = local.name_prefix
  aws_region            = var.aws_region
  vpc_id                = module.vpc.vpc_id
  vpc_cidr              = module.vpc.vpc_cidr
  private_subnet_ids    = module.vpc.private_subnet_ids
  alb_security_group_id = module.alb_waf.alb_security_group_id
  execution_role_arn    = module.iam.execution_role_arn
  task_role_arns        = module.iam.task_role_arns
  target_group_arns     = module.alb_waf.target_group_arns
  app_secret_arn        = module.secrets.app_secret_arn
  rds_secret_arn        = module.secrets.rds_secret_arn
  raw_bucket_id         = module.s3.raw_bucket_id
  gold_bucket_id        = module.s3.gold_bucket_id
  db_endpoint           = module.rds.db_endpoint
  db_port               = module.rds.db_port
  services              = local.services
  image_uris            = local.image_uris
  kms_key_arn           = module.kms.key_arn
  tags                  = local.common_tags
}

module "observability" {
  source = "./modules/observability"

  name_prefix               = local.name_prefix
  aws_region                = var.aws_region
  alb_arn_suffix            = module.alb_waf.alb_arn_suffix
  target_group_arn_suffixes = module.alb_waf.target_group_arn_suffixes
  ecs_cluster_name          = module.ecs.cluster_name
  rds_instance_id           = module.rds.db_instance_id
  tags                      = local.common_tags
}
