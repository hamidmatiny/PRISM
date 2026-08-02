# Automatic rotation — closes Phase 6 CKV2_AWS_57 deferral (see CHECKOV_SKIPS.md history
# and docs/runbooks/secrets-rotation.md).

data "archive_file" "rotation" {
  type        = "zip"
  source_file = "${path.module}/lambda/rotate.py"
  output_path = "${path.module}/.build/rotate.zip"
}

data "aws_iam_policy_document" "rotation_assume" {
  statement {
    sid     = "LambdaAssume"
    effect  = "Allow"
    actions = ["sts:AssumeRole"]
    principals {
      type        = "Service"
      identifiers = ["lambda.amazonaws.com"]
    }
  }
}

resource "aws_iam_role" "rotation" {
  name               = "${var.name_prefix}-secrets-rotation"
  assume_role_policy = data.aws_iam_policy_document.rotation_assume.json
  tags               = merge(var.tags, { Role = "secrets-rotation" })
}

data "aws_iam_policy_document" "rotation" {
  statement {
    sid    = "RotatePrismSecrets"
    effect = "Allow"
    actions = [
      "secretsmanager:DescribeSecret",
      "secretsmanager:GetSecretValue",
      "secretsmanager:PutSecretValue",
      "secretsmanager:UpdateSecretVersionStage",
    ]
    resources = [
      aws_secretsmanager_secret.rds.arn,
      aws_secretsmanager_secret.app.arn,
    ]
  }

  statement {
    sid       = "AllowPasswordGeneration"
    effect    = "Allow"
    actions   = ["secretsmanager:GetRandomPassword"]
    resources = ["*"]
  }

  statement {
    sid    = "DecryptEncryptSecretPayload"
    effect = "Allow"
    actions = [
      "kms:Decrypt",
      "kms:Encrypt",
      "kms:GenerateDataKey",
      "kms:DescribeKey",
    ]
    resources = [var.kms_key_arn]
  }

  statement {
    sid    = "WriteRotationLogs"
    effect = "Allow"
    actions = [
      "logs:CreateLogGroup",
      "logs:CreateLogStream",
      "logs:PutLogEvents",
    ]
    resources = ["arn:aws:logs:*:*:log-group:/aws/lambda/${var.name_prefix}-secrets-rotation*"]
  }
}

resource "aws_iam_role_policy" "rotation" {
  name   = "${var.name_prefix}-secrets-rotation"
  role   = aws_iam_role.rotation.id
  policy = data.aws_iam_policy_document.rotation.json
}

resource "aws_cloudwatch_log_group" "rotation" {
  name              = "/aws/lambda/${var.name_prefix}-secrets-rotation"
  retention_in_days = 365
  kms_key_id        = var.kms_key_arn
  tags              = var.tags
}

resource "aws_lambda_function" "rotation" {
  #checkov:skip=CKV_AWS_117: Rotation Lambda VPC attachment is apply-time (needs RDS SG); plan scaffold uses regional endpoint — see secrets-rotation runbook
  #checkov:skip=CKV_AWS_116: DLQ optional for rotation; failures surface in Secrets Manager rotation status
  #checkov:skip=CKV_AWS_50: X-Ray optional; CloudWatch logs + Secrets Manager events cover audit
  #checkov:skip=CKV_AWS_115: Reserved concurrency not required for low-frequency rotation
  #checkov:skip=CKV_AWS_272: Code signing deferred; artifact is repo-built zip from this module
  function_name    = "${var.name_prefix}-secrets-rotation"
  description      = "PRISM Secrets Manager rotation (RDS + app)"
  role             = aws_iam_role.rotation.arn
  handler          = "rotate.handler"
  runtime          = "python3.12"
  timeout          = 60
  memory_size      = 256
  filename         = data.archive_file.rotation.output_path
  source_code_hash = data.archive_file.rotation.output_base64sha256
  depends_on       = [aws_cloudwatch_log_group.rotation]
  tags             = var.tags

  environment {
    variables = {
      PRISM_ROTATION_APPLY_RDS = "false"
    }
  }

  kms_key_arn = var.kms_key_arn
}

resource "aws_lambda_permission" "allow_secretsmanager_rds" {
  statement_id  = "AllowSecretsManagerRds"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.rotation.function_name
  principal     = "secretsmanager.amazonaws.com"
  source_arn    = aws_secretsmanager_secret.rds.arn
}

resource "aws_lambda_permission" "allow_secretsmanager_app" {
  statement_id  = "AllowSecretsManagerApp"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.rotation.function_name
  principal     = "secretsmanager.amazonaws.com"
  source_arn    = aws_secretsmanager_secret.app.arn
}

# aws_secretsmanager_secret_rotation.{rds,app} live in main.tf next to the secrets.
