package prism.consecutive_failures_test

import rego.v1

import data.prism.consecutive_failures

test_no_trip_below_threshold if {
	not consecutive_failures.trip with input as {"consecutive_qa_failures": 2}
}

test_trips_at_threshold if {
	consecutive_failures.trip with input as {"consecutive_qa_failures": 3}
}

test_trips_above_threshold if {
	consecutive_failures.trip with input as {"consecutive_qa_failures": 5}
}
