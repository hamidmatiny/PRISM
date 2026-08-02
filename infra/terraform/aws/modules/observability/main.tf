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
variable "alb_arn_suffix" { type = string }
variable "target_group_arn_suffixes" { type = map(string) }
variable "ecs_cluster_name" { type = string }
variable "rds_instance_id" { type = string }
variable "tags" {
  type    = map(string)
  default = {}
}

locals {
  # Every ECS-bound service from Phase 6 IAM/ECS modules.
  services = toset([
    "ingestion",
    "cv-service",
    "activation-gateway",
    "control-plane",
    "ai-copilot",
  ])

  # Latency (seconds), error count / 60s, CPU saturation (%)
  latency_thresholds = {
    "ingestion"          = 2
    "cv-service"         = 5
    "activation-gateway" = 2
    "control-plane"      = 2
    "ai-copilot"         = 3
  }
  error_thresholds = {
    "ingestion"          = 10
    "cv-service"         = 5
    "activation-gateway" = 5
    "control-plane"      = 5
    "ai-copilot"         = 5
  }
  cpu_thresholds = {
    "ingestion"          = 85
    "cv-service"         = 85
    "activation-gateway" = 80
    "control-plane"      = 80
    "ai-copilot"         = 80
  }
}

# Fleet-wide ops overview (kept from Phase 6).
resource "aws_cloudwatch_dashboard" "prism" {
  dashboard_name = "${var.name_prefix}-ops"

  dashboard_body = jsonencode({
    widgets = [
      {
        type   = "metric"
        x      = 0
        y      = 0
        width  = 12
        height = 6
        properties = {
          title  = "ALB 5XX"
          region = var.aws_region
          metrics = [
            ["AWS/ApplicationELB", "HTTPCode_Target_5XX_Count", "LoadBalancer", var.alb_arn_suffix, { stat = "Sum" }],
          ]
          period = 60
        }
      },
      {
        type   = "metric"
        x      = 12
        y      = 0
        width  = 12
        height = 6
        properties = {
          title  = "ALB Target Response Time"
          region = var.aws_region
          metrics = [
            ["AWS/ApplicationELB", "TargetResponseTime", "LoadBalancer", var.alb_arn_suffix, { stat = "p95" }],
          ]
          period = 60
        }
      },
      {
        type   = "metric"
        x      = 0
        y      = 6
        width  = 12
        height = 6
        properties = {
          title  = "RDS CPU"
          region = var.aws_region
          metrics = [
            ["AWS/RDS", "CPUUtilization", "DBInstanceIdentifier", var.rds_instance_id, { stat = "Average" }],
          ]
          period = 60
        }
      },
      {
        type   = "metric"
        x      = 12
        y      = 6
        width  = 12
        height = 6
        properties = {
          title  = "Review queue depth"
          region = var.aws_region
          metrics = [
            ["PRISM", "ReviewQueueDepth", { stat = "Maximum" }],
          ]
          period = 60
        }
      }
    ]
  })
}

# Per-service LES dashboards: Latency / Errors / Saturation.
resource "aws_cloudwatch_dashboard" "service" {
  for_each       = local.services
  dashboard_name = "${var.name_prefix}-${each.key}"

  dashboard_body = jsonencode({
    widgets = [
      {
        type   = "metric"
        x      = 0
        y      = 0
        width  = 8
        height = 6
        properties = {
          title   = "${each.key} latency p95"
          region  = var.aws_region
          metrics = [
            [
              "AWS/ApplicationELB", "TargetResponseTime",
              "TargetGroup", lookup(var.target_group_arn_suffixes, each.key, ""),
              "LoadBalancer", var.alb_arn_suffix,
              { stat = "p95", label = "p95" },
            ],
          ]
          period = 60
          yAxis  = { left = { min = 0 } }
        }
      },
      {
        type   = "metric"
        x      = 8
        y      = 0
        width  = 8
        height = 6
        properties = {
          title  = "${each.key} 5XX"
          region = var.aws_region
          metrics = [
            [
              "AWS/ApplicationELB", "HTTPCode_Target_5XX_Count",
              "TargetGroup", lookup(var.target_group_arn_suffixes, each.key, ""),
              "LoadBalancer", var.alb_arn_suffix,
              { stat = "Sum", label = "5xx" },
            ],
            [
              "AWS/ApplicationELB", "HTTPCode_Target_4XX_Count",
              "TargetGroup", lookup(var.target_group_arn_suffixes, each.key, ""),
              "LoadBalancer", var.alb_arn_suffix,
              { stat = "Sum", label = "4xx" },
            ],
          ]
          period = 60
        }
      },
      {
        type   = "metric"
        x      = 16
        y      = 0
        width  = 8
        height = 6
        properties = {
          title  = "${each.key} saturation (CPU / memory)"
          region = var.aws_region
          metrics = [
            ["AWS/ECS", "CPUUtilization", "ClusterName", var.ecs_cluster_name, "ServiceName", each.key, { stat = "Average", label = "cpu" }],
            ["AWS/ECS", "MemoryUtilization", "ClusterName", var.ecs_cluster_name, "ServiceName", each.key, { stat = "Average", label = "mem" }],
          ]
          period = 60
          yAxis  = { left = { min = 0, max = 100 } }
        }
      },
      {
        type   = "metric"
        x      = 0
        y      = 6
        width  = 12
        height = 6
        properties = {
          title  = "${each.key} running tasks"
          region = var.aws_region
          metrics = [
            ["ECS/ContainerInsights", "RunningTaskCount", "ClusterName", var.ecs_cluster_name, "ServiceName", each.key, { stat = "Average" }],
          ]
          period = 60
        }
      },
      {
        type   = "metric"
        x      = 12
        y      = 6
        width  = 12
        height = 6
        properties = {
          title  = "${each.key} request count"
          region = var.aws_region
          metrics = [
            [
              "AWS/ApplicationELB", "RequestCount",
              "TargetGroup", lookup(var.target_group_arn_suffixes, each.key, ""),
              "LoadBalancer", var.alb_arn_suffix,
              { stat = "Sum" },
            ],
          ]
          period = 60
        }
      }
    ]
  })
}

resource "aws_cloudwatch_metric_alarm" "alb_5xx" {
  alarm_name          = "${var.name_prefix}-alb-5xx"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = 2
  metric_name         = "HTTPCode_Target_5XX_Count"
  namespace           = "AWS/ApplicationELB"
  period              = 60
  statistic           = "Sum"
  threshold           = 5
  alarm_description   = "ALB target 5XX error rate elevated"
  treat_missing_data  = "notBreaching"
  dimensions = {
    LoadBalancer = var.alb_arn_suffix
  }
  tags = var.tags
}

resource "aws_cloudwatch_metric_alarm" "alb_latency" {
  alarm_name          = "${var.name_prefix}-alb-latency-p95"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = 3
  metric_name         = "TargetResponseTime"
  namespace           = "AWS/ApplicationELB"
  period              = 60
  extended_statistic  = "p95"
  threshold           = 2
  alarm_description   = "ALB p95 target latency > 2s"
  treat_missing_data  = "notBreaching"
  dimensions = {
    LoadBalancer = var.alb_arn_suffix
  }
  tags = var.tags
}

resource "aws_cloudwatch_metric_alarm" "rds_cpu" {
  alarm_name          = "${var.name_prefix}-rds-cpu"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = 3
  metric_name         = "CPUUtilization"
  namespace           = "AWS/RDS"
  period              = 60
  statistic           = "Average"
  threshold           = 80
  alarm_description   = "RDS CPU > 80%"
  dimensions = {
    DBInstanceIdentifier = var.rds_instance_id
  }
  tags = var.tags
}

resource "aws_cloudwatch_metric_alarm" "service_cpu" {
  for_each            = local.services
  alarm_name          = "${var.name_prefix}-${each.key}-cpu"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = 3
  metric_name         = "CPUUtilization"
  namespace           = "AWS/ECS"
  period              = 60
  statistic           = "Average"
  threshold           = local.cpu_thresholds[each.key]
  alarm_description   = "${each.key} CPU > ${local.cpu_thresholds[each.key]}%"
  treat_missing_data  = "notBreaching"
  dimensions = {
    ClusterName = var.ecs_cluster_name
    ServiceName = each.key
  }
  tags = var.tags
}

resource "aws_cloudwatch_metric_alarm" "service_latency" {
  for_each            = local.services
  alarm_name          = "${var.name_prefix}-${each.key}-latency-p95"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = 3
  metric_name         = "TargetResponseTime"
  namespace           = "AWS/ApplicationELB"
  period              = 60
  extended_statistic  = "p95"
  threshold           = local.latency_thresholds[each.key]
  alarm_description   = "${each.key} p95 latency > ${local.latency_thresholds[each.key]}s"
  treat_missing_data  = "notBreaching"
  dimensions = {
    LoadBalancer = var.alb_arn_suffix
    TargetGroup  = lookup(var.target_group_arn_suffixes, each.key, "")
  }
  tags = var.tags
}

resource "aws_cloudwatch_metric_alarm" "service_5xx" {
  for_each            = local.services
  alarm_name          = "${var.name_prefix}-${each.key}-5xx"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = 2
  metric_name         = "HTTPCode_Target_5XX_Count"
  namespace           = "AWS/ApplicationELB"
  period              = 60
  statistic           = "Sum"
  threshold           = local.error_thresholds[each.key]
  alarm_description   = "${each.key} 5XX count elevated"
  treat_missing_data  = "notBreaching"
  dimensions = {
    LoadBalancer = var.alb_arn_suffix
    TargetGroup  = lookup(var.target_group_arn_suffixes, each.key, "")
  }
  tags = var.tags
}

resource "aws_cloudwatch_metric_alarm" "control_plane_tasks" {
  alarm_name          = "${var.name_prefix}-control-plane-task-count"
  comparison_operator = "LessThanThreshold"
  evaluation_periods  = 2
  metric_name         = "RunningTaskCount"
  namespace           = "ECS/ContainerInsights"
  period              = 60
  statistic           = "Average"
  threshold           = 1
  alarm_description   = "control-plane running tasks below 1 (queue processing at risk)"
  treat_missing_data  = "breaching"
  dimensions = {
    ClusterName = var.ecs_cluster_name
    ServiceName = "control-plane"
  }
  tags = var.tags
}

# Populated by control-plane EMF when PRISM_ENV=aws (see prism_control.metrics).
resource "aws_cloudwatch_metric_alarm" "review_queue_depth" {
  alarm_name          = "${var.name_prefix}-review-queue-depth"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = 2
  metric_name         = "ReviewQueueDepth"
  namespace           = "PRISM"
  period              = 60
  statistic           = "Maximum"
  threshold           = 100
  alarm_description   = "Human-review queue depth > 100"
  treat_missing_data  = "notBreaching"
  tags                = var.tags
}

output "dashboard_name" { value = aws_cloudwatch_dashboard.prism.dashboard_name }
output "service_dashboard_names" {
  value = { for k, d in aws_cloudwatch_dashboard.service : k => d.dashboard_name }
}
output "alarm_names" {
  value = concat(
    [
      aws_cloudwatch_metric_alarm.alb_5xx.alarm_name,
      aws_cloudwatch_metric_alarm.alb_latency.alarm_name,
      aws_cloudwatch_metric_alarm.rds_cpu.alarm_name,
      aws_cloudwatch_metric_alarm.control_plane_tasks.alarm_name,
      aws_cloudwatch_metric_alarm.review_queue_depth.alarm_name,
    ],
    [for a in aws_cloudwatch_metric_alarm.service_cpu : a.alarm_name],
    [for a in aws_cloudwatch_metric_alarm.service_latency : a.alarm_name],
    [for a in aws_cloudwatch_metric_alarm.service_5xx : a.alarm_name],
  )
}
