# PRISM trip policy — drifted feature count from drift-monitor observations.
package prism.drift_count

import rego.v1

threshold := 2

default trip := false

trip if {
	input.drifted_feature_count >= threshold
}
