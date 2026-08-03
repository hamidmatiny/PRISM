package prism.drift_count_test

import rego.v1

import data.prism.drift_count

test_no_trip_below_threshold if {
	not drift_count.trip with input as {"drifted_feature_count": 1}
}

test_trips_at_threshold if {
	drift_count.trip with input as {"drifted_feature_count": 2}
}

test_trips_above_threshold if {
	drift_count.trip with input as {"drifted_feature_count": 5}
}
