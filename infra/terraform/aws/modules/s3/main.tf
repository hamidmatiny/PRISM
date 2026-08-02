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
variable "raw_glacier_transition_days" { type = number }
variable "kms_key_arn" { type = string }
variable "aws_account_id" { type = string }
variable "elb_account_id" { type = string }
variable "tags" {
  type    = map(string)
  default = {}
}

# Separate resources (not for_each) so checkov graph checks attach reliably.

resource "aws_s3_bucket" "raw" {
  #checkov:skip=CKV_AWS_144: CRR deferred to Phase 7 Azure DR — see CHECKOV_SKIPS.md
  #checkov:skip=CKV2_AWS_62: Event notifications deferred until real consumers exist — see CHECKOV_SKIPS.md
  bucket        = "${var.name_prefix}-raw"
  force_destroy = false
  tags          = merge(var.tags, { Name = "${var.name_prefix}-raw", Zone = "raw" })
}

resource "aws_s3_bucket" "gold" {
  #checkov:skip=CKV_AWS_144: CRR deferred to Phase 7 Azure DR — see CHECKOV_SKIPS.md
  #checkov:skip=CKV2_AWS_62: Event notifications deferred until real consumers exist — see CHECKOV_SKIPS.md
  bucket        = "${var.name_prefix}-gold"
  force_destroy = false
  tags          = merge(var.tags, { Name = "${var.name_prefix}-gold", Zone = "gold" })
}

resource "aws_s3_bucket" "logs" {
  #checkov:skip=CKV_AWS_145: ALB access-log delivery requires SSE-S3 (not SSE-KMS)
  #checkov:skip=CKV_AWS_144: CRR deferred to Phase 7 Azure DR — see CHECKOV_SKIPS.md
  #checkov:skip=CKV2_AWS_62: Access-logs bucket has no processing consumer — see CHECKOV_SKIPS.md
  bucket        = "${var.name_prefix}-access-logs"
  force_destroy = false
  tags          = merge(var.tags, { Name = "${var.name_prefix}-access-logs", Zone = "logs" })
}

resource "aws_s3_bucket_public_access_block" "raw" {
  bucket                  = aws_s3_bucket.raw.id
  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

resource "aws_s3_bucket_public_access_block" "gold" {
  bucket                  = aws_s3_bucket.gold.id
  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

resource "aws_s3_bucket_public_access_block" "logs" {
  bucket                  = aws_s3_bucket.logs.id
  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

resource "aws_s3_bucket_versioning" "raw" {
  bucket = aws_s3_bucket.raw.id
  versioning_configuration { status = "Enabled" }
}

resource "aws_s3_bucket_versioning" "gold" {
  bucket = aws_s3_bucket.gold.id
  versioning_configuration { status = "Enabled" }
}

resource "aws_s3_bucket_versioning" "logs" {
  bucket = aws_s3_bucket.logs.id
  versioning_configuration { status = "Enabled" }
}

resource "aws_s3_bucket_server_side_encryption_configuration" "raw" {
  bucket = aws_s3_bucket.raw.id
  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm     = "aws:kms"
      kms_master_key_id = var.kms_key_arn
    }
    bucket_key_enabled = true
  }
}

resource "aws_s3_bucket_server_side_encryption_configuration" "gold" {
  bucket = aws_s3_bucket.gold.id
  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm     = "aws:kms"
      kms_master_key_id = var.kms_key_arn
    }
    bucket_key_enabled = true
  }
}

resource "aws_s3_bucket_server_side_encryption_configuration" "logs" {
  bucket = aws_s3_bucket.logs.id
  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm = "AES256"
    }
  }
}

resource "aws_s3_bucket_logging" "raw" {
  bucket = aws_s3_bucket.raw.id

  target_bucket = aws_s3_bucket.logs.id
  target_prefix = "s3-access-logs/raw/"
}

resource "aws_s3_bucket_logging" "gold" {
  bucket = aws_s3_bucket.gold.id

  target_bucket = aws_s3_bucket.logs.id
  target_prefix = "s3-access-logs/gold/"
}

resource "aws_s3_bucket_lifecycle_configuration" "raw" {
  bucket = aws_s3_bucket.raw.id

  rule {
    id     = "abort-mpu"
    status = "Enabled"
    filter {}
    abort_incomplete_multipart_upload {
      days_after_initiation = 7
    }
  }

  rule {
    id     = "raw-to-glacier"
    status = "Enabled"

    filter {
      prefix = "bronze/"
    }

    transition {
      days          = var.raw_glacier_transition_days
      storage_class = "GLACIER"
    }

    noncurrent_version_transition {
      noncurrent_days = var.raw_glacier_transition_days
      storage_class   = "GLACIER"
    }
  }
}

resource "aws_s3_bucket_lifecycle_configuration" "gold" {
  bucket = aws_s3_bucket.gold.id

  rule {
    id     = "abort-mpu"
    status = "Enabled"
    filter {}
    abort_incomplete_multipart_upload {
      days_after_initiation = 7
    }
  }
}

resource "aws_s3_bucket_lifecycle_configuration" "logs" {
  bucket = aws_s3_bucket.logs.id

  rule {
    id     = "expire-access-logs"
    status = "Enabled"
    filter {}
    expiration {
      days = 365
    }
    abort_incomplete_multipart_upload {
      days_after_initiation = 7
    }
  }
}

resource "aws_s3_bucket_policy" "logs" {
  bucket = aws_s3_bucket.logs.id
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid       = "AllowELBLogDelivery"
        Effect    = "Allow"
        Principal = { AWS = "arn:aws:iam::${var.elb_account_id}:root" }
        Action    = "s3:PutObject"
        Resource  = "${aws_s3_bucket.logs.arn}/alb-access-logs/AWSLogs/${var.aws_account_id}/*"
      },
      {
        Sid       = "AllowELBLogDeliveryAclCheck"
        Effect    = "Allow"
        Principal = { AWS = "arn:aws:iam::${var.elb_account_id}:root" }
        Action    = "s3:GetBucketAcl"
        Resource  = aws_s3_bucket.logs.arn
      },
      {
        Sid       = "AllowS3LogDelivery"
        Effect    = "Allow"
        Principal = { Service = "logging.s3.amazonaws.com" }
        Action    = "s3:PutObject"
        Resource  = "${aws_s3_bucket.logs.arn}/s3-access-logs/*"
        Condition = {
          StringEquals = {
            "aws:SourceAccount" = var.aws_account_id
          }
        }
      },
      {
        Sid       = "DenyInsecureTransport"
        Effect    = "Deny"
        Principal = "*"
        Action    = "s3:*"
        Resource = [
          aws_s3_bucket.logs.arn,
          "${aws_s3_bucket.logs.arn}/*",
        ]
        Condition = {
          Bool = { "aws:SecureTransport" = "false" }
        }
      }
    ]
  })
}

resource "aws_s3_bucket_policy" "raw" {
  bucket = aws_s3_bucket.raw.id
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Sid       = "DenyInsecureTransport"
      Effect    = "Deny"
      Principal = "*"
      Action    = "s3:*"
      Resource = [
        aws_s3_bucket.raw.arn,
        "${aws_s3_bucket.raw.arn}/*",
      ]
      Condition = {
        Bool = { "aws:SecureTransport" = "false" }
      }
    }]
  })
}

resource "aws_s3_bucket_policy" "gold" {
  bucket = aws_s3_bucket.gold.id
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Sid       = "DenyInsecureTransport"
      Effect    = "Deny"
      Principal = "*"
      Action    = "s3:*"
      Resource = [
        aws_s3_bucket.gold.arn,
        "${aws_s3_bucket.gold.arn}/*",
      ]
      Condition = {
        Bool = { "aws:SecureTransport" = "false" }
      }
    }]
  })
}

output "raw_bucket_id" { value = aws_s3_bucket.raw.id }
output "raw_bucket_arn" { value = aws_s3_bucket.raw.arn }
output "gold_bucket_id" { value = aws_s3_bucket.gold.id }
output "gold_bucket_arn" { value = aws_s3_bucket.gold.arn }
output "logs_bucket_id" { value = aws_s3_bucket.logs.id }
output "logs_bucket_arn" { value = aws_s3_bucket.logs.arn }
