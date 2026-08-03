# Aggregated trip decision — priority matches Phase 14's Python order:
# quarantine_rate → consecutive_qa_failures → drifted_features.
package prism.trip

import rego.v1

import data.prism.consecutive_failures
import data.prism.drift_count
import data.prism.quarantine_rate

default reason := null

reason := "quarantine_rate" if quarantine_rate.trip

reason := "consecutive_qa_failures" if {
	not quarantine_rate.trip
	consecutive_failures.trip
}

reason := "drifted_features" if {
	not quarantine_rate.trip
	not consecutive_failures.trip
	drift_count.trip
}

decision := {
	"trip": reason != null,
	"reason": reason,
	"policy_engine": "opa",
}
