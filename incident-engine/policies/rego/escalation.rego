# PRISM escalation routing — maps trip reason → severity / notify targets.
# Consumed by incident-engine's mock webhook payload (no real Slack/PagerDuty).
package prism.escalation

import rego.v1

default route := {
	"channel": "mock_webhook",
	"severity": "info",
	"notify": ["ops"],
	"policy": "unknown",
}

route := {
	"channel": "mock_webhook",
	"severity": "medium",
	"notify": ["ops"],
	"policy": "quarantine_rate",
} if input.reason == "quarantine_rate"

route := {
	"channel": "mock_webhook",
	"severity": "medium",
	"notify": ["qa", "ops"],
	"policy": "consecutive_failures",
} if input.reason == "consecutive_qa_failures"

route := {
	"channel": "mock_webhook",
	"severity": "high",
	"notify": ["oncall", "ops"],
	"policy": "drift_count",
} if input.reason == "drifted_features"
