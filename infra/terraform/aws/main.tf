# AWS platform root — Phase 0 scaffold.
# Real VPC / ALB / ECS / RDS / S3 modules land in Phase 6.
# ADR-001: CI runs validate / tflint / checkov only; humans run apply.

resource "null_resource" "phase0_scaffold" {
  triggers = {
    project     = var.project
    environment = var.environment
    cloud       = "aws"
    phase       = "0"
  }
}
