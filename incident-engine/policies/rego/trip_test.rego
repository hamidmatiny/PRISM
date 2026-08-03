package prism.trip_test

import rego.v1

import data.prism.trip

test_no_trip_clean if {
	d := trip.decision with input as {
		"quarantine_window": [false, false, false, false, false],
		"consecutive_qa_failures": 0,
		"drifted_feature_count": 0,
	}
	not d.trip
	d.reason == null
}

test_quarantine_priority_over_drift if {
	d := trip.decision with input as {
		"quarantine_window": [true, true, true, true, true],
		"consecutive_qa_failures": 0,
		"drifted_feature_count": 5,
	}
	d.trip
	d.reason == "quarantine_rate"
}

test_qa_when_no_quarantine if {
	d := trip.decision with input as {
		"quarantine_window": [false, false, false, false, false],
		"consecutive_qa_failures": 3,
		"drifted_feature_count": 0,
	}
	d.reason == "consecutive_qa_failures"
}

test_drift_when_others_clear if {
	d := trip.decision with input as {
		"quarantine_window": [false, false, false, false, false],
		"consecutive_qa_failures": 0,
		"drifted_feature_count": 2,
	}
	d.reason == "drifted_features"
}
