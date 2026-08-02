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
variable "vpc_id" { type = string }
variable "vpc_cidr" { type = string }
variable "private_subnet_ids" { type = list(string) }
variable "alb_security_group_id" { type = string }
variable "execution_role_arn" { type = string }
variable "task_role_arns" { type = map(string) }
variable "target_group_arns" { type = map(string) }
variable "app_secret_arn" { type = string }
variable "rds_secret_arn" { type = string }
variable "raw_bucket_id" { type = string }
variable "gold_bucket_id" { type = string }
variable "db_endpoint" { type = string }
variable "db_port" { type = number }
variable "services" {
  type = map(object({
    port              = number
    path_patterns     = list(string)
    cpu               = number
    memory            = number
    desired_count     = number
    health_check_path = string
  }))
}
variable "image_uris" { type = map(string) }
variable "kms_key_arn" { type = string }
variable "tags" {
  type    = map(string)
  default = {}
}

resource "aws_cloudwatch_log_group" "service" {
  for_each          = var.services
  name              = "/ecs/${var.name_prefix}/${each.key}"
  retention_in_days = 365
  kms_key_id        = var.kms_key_arn
  tags              = merge(var.tags, { Service = each.key })
}

resource "aws_ecs_cluster" "this" {
  name = "${var.name_prefix}-ecs"

  setting {
    name  = "containerInsights"
    value = "enabled"
  }

  tags = merge(var.tags, { Name = "${var.name_prefix}-ecs" })
}

resource "aws_service_discovery_http_namespace" "this" {
  name        = "${var.name_prefix}.local"
  description = "PRISM Service Connect namespace"
  tags        = var.tags
}

resource "aws_security_group" "tasks" {
  name        = "${var.name_prefix}-ecs-tasks"
  description = "ECS Fargate tasks"
  vpc_id      = var.vpc_id

  ingress {
    description     = "From ALB"
    from_port       = 0
    to_port         = 65535
    protocol        = "tcp"
    security_groups = [var.alb_security_group_id]
  }

  ingress {
    description = "Service Connect within VPC"
    from_port   = 0
    to_port     = 65535
    protocol    = "tcp"
    cidr_blocks = [var.vpc_cidr]
  }

  egress {
    description = "HTTPS to AWS APIs / VPC endpoints"
    from_port   = 443
    to_port     = 443
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
  }

  egress {
    description = "Postgres to RDS in VPC"
    from_port   = 5432
    to_port     = 5432
    protocol    = "tcp"
    cidr_blocks = [var.vpc_cidr]
  }

  egress {
    description = "Service Connect HTTP within VPC"
    from_port   = 9100
    to_port     = 9105
    protocol    = "tcp"
    cidr_blocks = [var.vpc_cidr]
  }

  tags = merge(var.tags, { Name = "${var.name_prefix}-ecs-tasks-sg" })
}

resource "aws_ecs_task_definition" "service" {
  for_each = var.services

  family                   = "${var.name_prefix}-${each.key}"
  requires_compatibilities = ["FARGATE"]
  network_mode             = "awsvpc"
  cpu                      = each.value.cpu
  memory                   = each.value.memory
  execution_role_arn       = var.execution_role_arn
  task_role_arn            = var.task_role_arns[each.key]

  container_definitions = jsonencode([
    {
      name      = each.key
      image     = var.image_uris[each.key]
      essential = true
      portMappings = [
        {
          name          = each.key
          containerPort = each.value.port
          hostPort      = each.value.port
          protocol      = "tcp"
          appProtocol   = "http"
        }
      ]
      environment = [
        { name = "PRISM_ENV", value = "aws" },
        { name = "AWS_REGION", value = var.aws_region },
        { name = "PRISM_RAW_BUCKET", value = var.raw_bucket_id },
        { name = "PRISM_GOLD_BUCKET", value = var.gold_bucket_id },
        { name = "PRISM_SERVICE_CONNECT_NS", value = aws_service_discovery_http_namespace.this.name },
      ]
      secrets = concat(
        [
          {
            name      = "APP_SECRETS_JSON"
            valueFrom = var.app_secret_arn
          }
        ],
        each.key == "control-plane" ? [
          {
            name      = "DATABASE_SECRET_JSON"
            valueFrom = var.rds_secret_arn
          }
        ] : []
      )
      logConfiguration = {
        logDriver = "awslogs"
        options = {
          awslogs-group         = aws_cloudwatch_log_group.service[each.key].name
          awslogs-region        = var.aws_region
          awslogs-stream-prefix = "ecs"
        }
      }
      healthCheck = {
        command     = ["CMD-SHELL", "curl -f http://127.0.0.1:${each.value.port}${each.value.health_check_path} || exit 1"]
        interval    = 30
        timeout     = 5
        retries     = 3
        startPeriod = 60
      }
    }
  ])

  tags = merge(var.tags, { Service = each.key })
}

resource "aws_ecs_service" "service" {
  for_each = var.services

  name            = each.key
  cluster         = aws_ecs_cluster.this.id
  task_definition = aws_ecs_task_definition.service[each.key].arn
  desired_count   = each.value.desired_count
  launch_type     = "FARGATE"

  network_configuration {
    subnets          = var.private_subnet_ids
    security_groups  = [aws_security_group.tasks.id]
    assign_public_ip = false
  }

  load_balancer {
    target_group_arn = var.target_group_arns[each.key]
    container_name   = each.key
    container_port   = each.value.port
  }

  service_connect_configuration {
    enabled   = true
    namespace = aws_service_discovery_http_namespace.this.arn

    service {
      port_name      = each.key
      discovery_name = each.key
      client_alias {
        port     = each.value.port
        dns_name = each.key
      }
    }
  }

  deployment_minimum_healthy_percent = 50
  deployment_maximum_percent         = 200
  enable_execute_command             = false

  tags = merge(var.tags, { Service = each.key })

  depends_on = [aws_ecs_task_definition.service]
}

output "cluster_name" { value = aws_ecs_cluster.this.name }
output "cluster_arn" { value = aws_ecs_cluster.this.arn }
output "service_connect_namespace_arn" { value = aws_service_discovery_http_namespace.this.arn }
output "task_security_group_id" { value = aws_security_group.tasks.id }
output "log_group_arns" {
  value = { for k, lg in aws_cloudwatch_log_group.service : k => lg.arn }
}
output "log_group_names" {
  value = { for k, lg in aws_cloudwatch_log_group.service : k => lg.name }
}
