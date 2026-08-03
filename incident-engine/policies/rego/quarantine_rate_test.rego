package prism.quarantine_rate_test

import rego.v1

import data.prism.quarantine_rate

test_no_trip_when_window_incomplete if {
	not quarantine_rate.trip with input as {"quarantine_window": [true, true, true, true]}
}

test_no_trip_when_rate_at_or_below_threshold if {
	# 0/5 = 0.0
	not quarantine_rate.trip with input as {"quarantine_window": [false, false, false, false, false]}
}

test_trips_when_rate_exceeds_threshold if {
	# 1/5 = 0.20 > 0.15
	quarantine_rate.trip with input as {"quarantine_window": [true, false, false, false, false]}
}

test_trips_when_all_quarantined if {
	quarantine_rate.trip with input as {"quarantine_window": [true, true, true, true, true]}
}
