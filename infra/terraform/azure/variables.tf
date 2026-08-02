variable "project" {
  type        = string
  description = "Project name prefix"
  default     = "prism"
}

variable "environment" {
  type        = string
  description = "Environment name (dev / staging / prod)"
  default     = "dev"
}
