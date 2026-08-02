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
          title  = "ECS CPU (control-plane)"
          region = var.aws_region
          metrics = [
            ["AWS/ECS", "CPUUtilization", "ClusterName", var.ecs_cluster_name, "ServiceName", "control-plane", { stat = "Average" }],
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
        x      = 0
        y      = 12
        width  = 12
        height = 6
        properties = {
          title  = "Control-plane target response time"
          region = var.aws_region
          metrics = [
            ["AWS/ApplicationELB", "TargetResponseTime", "TargetGroup", lookup(var.target_group_arn_suffixes, "control-plane", ""), "LoadBalancer", var.alb_arn_suffix, { stat = "p95" }],
          ]
          period = 60
        }
      },
      {
        type   = "metric"
        x      = 12
        y      = 12
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

# Queue-depth stand-in: ECS RunningTaskCount drop for control-plane (review workers).
# Custom EMF metric PRISM/ReviewQueueDepth can replace this after Phase 10 wiring.
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

resource "aws_cloudwatch_metric_alarm" "cv_service_cpu" {
  alarm_name          = "${var.name_prefix}-cv-service-cpu"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = 3
  metric_name         = "CPUUtilization"
  namespace           = "AWS/ECS"
  period              = 60
  statistic           = "Average"
  threshold           = 85
  alarm_description   = "cv-service CPU > 85%"
  dimensions = {
    ClusterName = var.ecs_cluster_name
    ServiceName = "cv-service"
  }
  tags = var.tags
}

# Review-queue depth — control-plane / cv-service emit PRISM/ReviewQueueDepth via EMF.
# Alarm is wired now; metric population lands with production emitters (Phase 10 ops).
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
output "alarm_names" {
  value = [
    aws_cloudwatch_metric_alarm.alb_5xx.alarm_name,
    aws_cloudwatch_metric_alarm.alb_latency.alarm_name,
    aws_cloudwatch_metric_alarm.rds_cpu.alarm_name,
    aws_cloudwatch_metric_alarm.control_plane_tasks.alarm_name,
    aws_cloudwatch_metric_alarm.cv_service_cpu.alarm_name,
    aws_cloudwatch_metric_alarm.review_queue_depth.alarm_name,
  ]
}
