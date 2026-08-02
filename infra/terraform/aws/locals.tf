locals {
  name_prefix = "${var.project}-${var.environment}"

  common_tags = {
    Project     = var.project
    Environment = var.environment
    ManagedBy   = "terraform"
    Phase       = "6"
    CostSafety  = "ADR-001"
  }

  # Host port map from .cursor/rules/monorepo.mdc — container listen ports.
  services = {
    ingestion = {
      port              = 9105
      path_patterns     = ["/ingestion", "/ingestion/*", "/health/ingestion"]
      cpu               = 256
      memory            = 512
      desired_count     = 2
      health_check_path = "/health"
    }
    cv-service = {
      port              = 9102
      path_patterns     = ["/cv", "/cv/*"]
      cpu               = 512
      memory            = 1024
      desired_count     = 2
      health_check_path = "/health"
    }
    activation-gateway = {
      port              = 9103
      path_patterns     = ["/activation", "/activation/*"]
      cpu               = 256
      memory            = 512
      desired_count     = 2
      health_check_path = "/health"
    }
    control-plane = {
      port              = 9100
      path_patterns     = ["/api", "/api/*", "/admin", "/admin/*", "/health"]
      cpu               = 512
      memory            = 1024
      desired_count     = 2
      health_check_path = "/health"
    }
    ai-copilot = {
      port              = 9104
      path_patterns     = ["/copilot", "/copilot/*"]
      cpu               = 256
      memory            = 512
      desired_count     = 1
      health_check_path = "/health"
    }
  }

  image_uris = {
    for name, _ in local.services :
    name => "${var.ecr_repository_prefix}/${name}:${var.container_image_tag}"
  }
}
