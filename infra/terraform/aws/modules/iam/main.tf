# Least-privilege ECS task roles — hydra-data-factory style: explicit SIDs,
# resource ARNs only, no Action/Resource wildcards.
terraform {
  required_version = ">= 1.5.0"
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = ">= 5.0"
    }
  }
}

variable "name_prefix" { type = string }
variable "aws_region" { type = string }
variable "aws_account_id" { type = string }
variable "raw_bucket_arn" { type = string }
variable "gold_bucket_arn" { type = string }
variable "rds_secret_arn" { type = string }
variable "app_secret_arn" { type = string }
variable "kms_key_arn" { type = string }
variable "tags" {
  type    = map(string)
  default = {}
}

locals {
  services = toset(["ingestion", "cv-service", "activation-gateway", "control-plane", "ai-copilot"])
  # Constructed ARNs avoid a cycle with the ECS module (hydra-style explicit resources).
  log_group_arns = {
    for svc in local.services :
    svc => "arn:aws:logs:${var.aws_region}:${var.aws_account_id}:log-group:/ecs/${var.name_prefix}/${svc}"
  }
}

data "aws_iam_policy_document" "ecs_task_assume" {
  statement {
    sid     = "EcsTasksAssume"
    effect  = "Allow"
    actions = ["sts:AssumeRole"]
    principals {
      type        = "Service"
      identifiers = ["ecs-tasks.amazonaws.com"]
    }
  }
}

resource "aws_iam_role" "execution" {
  name               = "${var.name_prefix}-ecs-execution"
  assume_role_policy = data.aws_iam_policy_document.ecs_task_assume.json
  tags               = merge(var.tags, { Role = "ecs-execution" })
}

data "aws_iam_policy_document" "execution" {
  statement {
    sid    = "PullSecretsForTaskStart"
    effect = "Allow"
    actions = [
      "secretsmanager:GetSecretValue",
      "secretsmanager:DescribeSecret",
    ]
    resources = [
      var.rds_secret_arn,
      var.app_secret_arn,
    ]
  }

  statement {
    sid    = "WriteTaskLogs"
    effect = "Allow"
    actions = [
      "logs:CreateLogStream",
      "logs:PutLogEvents",
    ]
    resources = [for arn in values(local.log_group_arns) : "${arn}:*"]
  }

  statement {
    sid    = "EcrAuth"
    effect = "Allow"
    actions = [
      "ecr:GetAuthorizationToken",
    ]
    # GetAuthorizationToken is account-scoped; AWS requires Resource=* for this action.
    # Scoped companion statement covers image pulls.
    resources = ["*"]
  }

  statement {
    sid    = "EcrPullPrismImages"
    effect = "Allow"
    actions = [
      "ecr:BatchCheckLayerAvailability",
      "ecr:GetDownloadUrlForLayer",
      "ecr:BatchGetImage",
    ]
    resources = [
      "arn:aws:ecr:${var.aws_region}:${var.aws_account_id}:repository/prism-*",
    ]
  }

  statement {
    sid    = "DecryptPlatformSecrets"
    effect = "Allow"
    actions = [
      "kms:Decrypt",
      "kms:DescribeKey",
    ]
    resources = [var.kms_key_arn]
  }
}

resource "aws_iam_role_policy" "execution" {
  name   = "${var.name_prefix}-ecs-execution"
  role   = aws_iam_role.execution.id
  policy = data.aws_iam_policy_document.execution.json
}

resource "aws_iam_role" "task" {
  for_each           = local.services
  name               = "${var.name_prefix}-task-${each.key}"
  assume_role_policy = data.aws_iam_policy_document.ecs_task_assume.json
  tags               = merge(var.tags, { Role = "ecs-task", Service = each.key })
}

# --- per-service least-privilege policies ---

data "aws_iam_policy_document" "ingestion" {
  statement {
    sid       = "ListRawBucket"
    effect    = "Allow"
    actions   = ["s3:ListBucket"]
    resources = [var.raw_bucket_arn]
    condition {
      test     = "StringLike"
      variable = "s3:prefix"
      values   = ["bronze", "bronze/*"]
    }
  }

  statement {
    sid    = "WriteRawBronze"
    effect = "Allow"
    actions = [
      "s3:PutObject",
      "s3:AbortMultipartUpload",
    ]
    resources = ["${var.raw_bucket_arn}/bronze/*"]
  }

  statement {
    sid       = "ReadAppSecret"
    effect    = "Allow"
    actions   = ["secretsmanager:GetSecretValue"]
    resources = [var.app_secret_arn]
  }

  statement {
    sid     = "WriteIngestionLogs"
    effect  = "Allow"
    actions = ["logs:CreateLogStream", "logs:PutLogEvents"]
    resources = [
      "${local.log_group_arns["ingestion"]}:*",
    ]
  }

  statement {
    sid       = "DecryptAppSecret"
    effect    = "Allow"
    actions   = ["kms:Decrypt"]
    resources = [var.kms_key_arn]
  }
}

data "aws_iam_policy_document" "cv_service" {
  statement {
    sid    = "ReadRawFrames"
    effect = "Allow"
    actions = [
      "s3:GetObject",
      "s3:ListBucket",
    ]
    resources = [
      var.raw_bucket_arn,
      "${var.raw_bucket_arn}/bronze/camera_frames/*",
    ]
  }

  statement {
    sid    = "WriteFindings"
    effect = "Allow"
    actions = [
      "s3:PutObject",
    ]
    resources = [
      "${var.gold_bucket_arn}/cv-findings/*",
      "${var.gold_bucket_arn}/cv-review-queue/*",
    ]
  }

  statement {
    sid       = "ReadAppSecret"
    effect    = "Allow"
    actions   = ["secretsmanager:GetSecretValue"]
    resources = [var.app_secret_arn]
  }

  statement {
    sid       = "WriteCvLogs"
    effect    = "Allow"
    actions   = ["logs:CreateLogStream", "logs:PutLogEvents"]
    resources = ["${local.log_group_arns["cv-service"]}:*"]
  }

  statement {
    sid       = "DecryptAppSecret"
    effect    = "Allow"
    actions   = ["kms:Decrypt"]
    resources = [var.kms_key_arn]
  }
}

data "aws_iam_policy_document" "activation_gateway" {
  statement {
    sid    = "ReadGoldTables"
    effect = "Allow"
    actions = [
      "s3:GetObject",
      "s3:ListBucket",
    ]
    resources = [
      var.gold_bucket_arn,
      "${var.gold_bucket_arn}/gold/*",
      "${var.gold_bucket_arn}/lakehouse/gold/*",
    ]
  }

  statement {
    sid       = "ReadAppSecret"
    effect    = "Allow"
    actions   = ["secretsmanager:GetSecretValue"]
    resources = [var.app_secret_arn]
  }

  statement {
    sid       = "WriteActivationLogs"
    effect    = "Allow"
    actions   = ["logs:CreateLogStream", "logs:PutLogEvents"]
    resources = ["${local.log_group_arns["activation-gateway"]}:*"]
  }

  statement {
    sid       = "DecryptAppSecret"
    effect    = "Allow"
    actions   = ["kms:Decrypt"]
    resources = [var.kms_key_arn]
  }
}

data "aws_iam_policy_document" "control_plane" {
  statement {
    sid    = "ReadWriteGoldFindings"
    effect = "Allow"
    actions = [
      "s3:GetObject",
      "s3:PutObject",
      "s3:ListBucket",
    ]
    resources = [
      var.gold_bucket_arn,
      "${var.gold_bucket_arn}/lakehouse/gold/cv_findings/*",
      "${var.gold_bucket_arn}/cv-review-queue/*",
    ]
  }

  statement {
    sid    = "ReadDbAndAppSecrets"
    effect = "Allow"
    actions = [
      "secretsmanager:GetSecretValue",
      "secretsmanager:DescribeSecret",
    ]
    resources = [
      var.rds_secret_arn,
      var.app_secret_arn,
    ]
  }

  statement {
    sid       = "WriteControlPlaneLogs"
    effect    = "Allow"
    actions   = ["logs:CreateLogStream", "logs:PutLogEvents"]
    resources = ["${local.log_group_arns["control-plane"]}:*"]
  }

  statement {
    sid       = "DecryptDbAndAppSecrets"
    effect    = "Allow"
    actions   = ["kms:Decrypt"]
    resources = [var.kms_key_arn]
  }
}

data "aws_iam_policy_document" "ai_copilot" {
  statement {
    sid    = "ReadGoldForTools"
    effect = "Allow"
    actions = [
      "s3:GetObject",
      "s3:ListBucket",
    ]
    resources = [
      var.gold_bucket_arn,
      "${var.gold_bucket_arn}/gold/*",
      "${var.gold_bucket_arn}/lakehouse/gold/*",
    ]
  }

  statement {
    sid       = "ReadAppSecret"
    effect    = "Allow"
    actions   = ["secretsmanager:GetSecretValue"]
    resources = [var.app_secret_arn]
  }

  statement {
    sid       = "WriteCopilotLogs"
    effect    = "Allow"
    actions   = ["logs:CreateLogStream", "logs:PutLogEvents"]
    resources = ["${local.log_group_arns["ai-copilot"]}:*"]
  }

  statement {
    sid       = "DecryptAppSecret"
    effect    = "Allow"
    actions   = ["kms:Decrypt"]
    resources = [var.kms_key_arn]
  }
}

resource "aws_iam_role_policy" "task" {
  for_each = local.services
  name     = "${var.name_prefix}-task-${each.key}"
  role     = aws_iam_role.task[each.key].id
  policy = {
    "ingestion"          = data.aws_iam_policy_document.ingestion.json
    "cv-service"         = data.aws_iam_policy_document.cv_service.json
    "activation-gateway" = data.aws_iam_policy_document.activation_gateway.json
    "control-plane"      = data.aws_iam_policy_document.control_plane.json
    "ai-copilot"         = data.aws_iam_policy_document.ai_copilot.json
  }[each.key]
}

output "execution_role_arn" { value = aws_iam_role.execution.arn }
output "task_role_arns" {
  value = { for k, r in aws_iam_role.task : k => r.arn }
}
