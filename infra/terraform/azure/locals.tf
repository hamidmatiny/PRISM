locals {
  name_prefix = "${var.project}-${var.environment}"

  common_tags = {
    Project     = var.project
    Environment = var.environment
    ManagedBy   = "terraform"
    Phase       = "7"
    CostSafety  = "ADR-001"
    Role        = "azure-dr-warm-standby"
  }

  # Mirror layout matches AWS lakehouse zones under the gold/raw buckets.
  lakehouse_containers = {
    gold   = "gold"
    silver = "silver"
    bronze = "bronze"
  }

  rpo_rto = {
    rpo_minutes              = var.rpo_minutes
    rto_hours                = var.rto_hours
    replication_cron_utc     = var.replication_schedule_cron
    notes                    = "RPO is job cadence bound; RTO assumes human-gated failover per azure-dr-failover.md"
    activation_failover_path = "docs/runbooks/azure-dr-failover.md"
  }
}
