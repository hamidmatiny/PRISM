package prism.escalation_test

import rego.v1

import data.prism.escalation

test_quarantine_route if {
	r := escalation.route with input as {"reason": "quarantine_rate"}
	r.severity == "medium"
	r.policy == "quarantine_rate"
}

test_qa_route if {
	r := escalation.route with input as {"reason": "consecutive_qa_failures"}
	r.notify == ["qa", "ops"]
}

test_drift_route_is_high if {
	r := escalation.route with input as {"reason": "drifted_features"}
	r.severity == "high"
	r.policy == "drift_count"
	"oncall" in r.notify
}

test_unknown_reason_defaults if {
	r := escalation.route with input as {"reason": "something_else"}
	r.severity == "info"
}
