# Azure DR root — Phase 0 scaffold.
# Warm-standby Databricks + ADLS Gen2 modules land in Phase 7.
# ADR-001: CI runs validate / tflint / checkov only; humans run apply.

resource "null_resource" "phase0_scaffold" {
  triggers = {
    project     = var.project
    environment = var.environment
    cloud       = "azure"
    phase       = "0"
  }
}
