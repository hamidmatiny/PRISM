terraform {
  required_version = ">= 1.5.0"
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = ">= 5.0"
    }
    random = {
      source  = "hashicorp/random"
      version = ">= 3.6"
    }
  }
}

variable "name_prefix" { type = string }
variable "kms_key_arn" { type = string }
variable "tags" {
  type    = map(string)
  default = {}
}

resource "random_password" "rds" {
  length           = 32
  special          = true
  override_special = "!#$%&*()-_=+[]{}<>:?"
}

resource "aws_secretsmanager_secret" "rds" {
  #checkov:skip=CKV2_AWS_57: Rotation Lambda deferred; secret is CMK-encrypted — see CHECKOV_SKIPS.md
  name                    = "${var.name_prefix}/rds/master"
  description             = "PRISM RDS master credentials"
  recovery_window_in_days = 7
  kms_key_id              = var.kms_key_arn
  tags                    = merge(var.tags, { Name = "${var.name_prefix}-rds-secret" })
}

resource "aws_secretsmanager_secret_version" "rds" {
  secret_id = aws_secretsmanager_secret.rds.id
  secret_string = jsonencode({
    username = "prism_admin"
    password = random_password.rds.result
    engine   = "postgres"
    port     = 5432
  })
}

resource "aws_secretsmanager_secret" "app" {
  #checkov:skip=CKV2_AWS_57: Rotation Lambda deferred; secret is CMK-encrypted — see CHECKOV_SKIPS.md
  name                    = "${var.name_prefix}/app/runtime"
  description             = "PRISM application runtime secrets (Django, tokens)"
  recovery_window_in_days = 7
  kms_key_id              = var.kms_key_arn
  tags                    = merge(var.tags, { Name = "${var.name_prefix}-app-secret" })
}

resource "random_password" "django" {
  length  = 64
  special = false
}

resource "aws_secretsmanager_secret_version" "app" {
  secret_id = aws_secretsmanager_secret.app.id
  secret_string = jsonencode({
    DJANGO_SECRET_KEY        = random_password.django.result
    PRISM_BOOTSTRAP_PASSWORD = random_password.django.result
  })
}

output "rds_secret_arn" { value = aws_secretsmanager_secret.rds.arn }
output "rds_secret_name" { value = aws_secretsmanager_secret.rds.name }
output "app_secret_arn" { value = aws_secretsmanager_secret.app.arn }
output "rds_username" { value = "prism_admin" }
output "rds_password" {
  value     = random_password.rds.result
  sensitive = true
}
