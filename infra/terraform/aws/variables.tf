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

variable "aws_region" {
  type        = string
  description = "AWS region (no data-source lookup — keeps CI plan offline)"
  default     = "us-east-1"
}

variable "aws_account_id" {
  type        = string
  description = "AWS account ID used to build ARNs without caller-identity data source"
  default     = "000000000000"
}

variable "availability_zones" {
  type        = list(string)
  description = "Exactly two AZs for multi-AZ layout (no AZ data source in CI)"
  default     = ["us-east-1a", "us-east-1b"]

  validation {
    condition     = length(var.availability_zones) == 2
    error_message = "Provide exactly two availability zones for multi-AZ."
  }
}

variable "vpc_cidr" {
  type        = string
  description = "VPC CIDR block"
  default     = "10.60.0.0/16"
}

variable "raw_glacier_transition_days" {
  type        = number
  description = "Days before S3 raw-zone objects transition to Glacier"
  default     = 90
}

variable "container_image_tag" {
  type        = string
  description = "Image tag for ECS task definitions (GHCR publish is release-gated)"
  default     = "latest"
}

variable "ecr_repository_prefix" {
  type        = string
  description = "Container registry prefix (no live ECR lookup in CI)"
  default     = "ghcr.io/hamidmatiny/prism"
}

variable "aws_skip_credentials_validation" {
  type        = bool
  description = "Skip AWS credential validation (true for CI plan; false for human apply)"
  default     = true
}

variable "aws_skip_requesting_account_id" {
  type        = bool
  description = "Skip STS GetCallerIdentity (true for CI plan; false for human apply)"
  default     = true
}

variable "alb_certificate_arn" {
  type        = string
  description = "ACM certificate ARN for HTTPS listener (placeholder OK for plan)"
  default     = ""
}

variable "enable_deletion_protection" {
  type        = bool
  description = "ALB/RDS deletion protection (true for prod; lab destroy may override)"
  default     = true
}

variable "elb_account_id" {
  type        = string
  description = "Regional ELB service account for ALB access-log bucket policy (us-east-1 default)"
  default     = "127311923021"
}
