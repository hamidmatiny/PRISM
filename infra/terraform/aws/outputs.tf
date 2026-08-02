output "phase" {
  description = "Platform phase marker"
  value       = "6"
}

output "vpc_id" {
  description = "VPC ID"
  value       = module.vpc.vpc_id
}

output "alb_dns_name" {
  description = "Public ALB DNS name"
  value       = module.alb_waf.alb_dns_name
}

output "ecs_cluster_name" {
  description = "ECS cluster name"
  value       = module.ecs.cluster_name
}

output "rds_endpoint" {
  description = "RDS PostgreSQL address"
  value       = module.rds.db_endpoint
}

output "raw_bucket_id" {
  description = "S3 raw/bronze bucket"
  value       = module.s3.raw_bucket_id
}

output "gold_bucket_id" {
  description = "S3 gold bucket"
  value       = module.s3.gold_bucket_id
}

output "service_connect_namespace" {
  description = "Service Connect HTTP namespace ARN"
  value       = module.ecs.service_connect_namespace_arn
}

output "dashboard_name" {
  description = "CloudWatch ops dashboard"
  value       = module.observability.dashboard_name
}

output "waf_acl_arn" {
  description = "WAFv2 Web ACL ARN attached to the ALB"
  value       = module.alb_waf.waf_arn
}

output "apply_warning" {
  description = "Reminder — never apply from CI/agents (ADR-001)"
  value       = "Human-gated terraform apply only. CI is validate/tflint/checkov/plan."
}
