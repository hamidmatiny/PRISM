# PRISM trip policy — quarantine rate over a rolling ingestion window.
# Thresholds live here (not in Python). Change via Rego review, not fsm.py.
package prism.quarantine_rate

import rego.v1

window_min := 5

threshold := 0.15

default trip := false

trip if {
	count(input.quarantine_window) >= window_min
	rate := count([x | some x in input.quarantine_window; x == true]) / count(input.quarantine_window)
	rate > threshold
}
