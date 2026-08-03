# PRISM trip policy — consecutive cv-service QA failures for one asset.
package prism.consecutive_failures

import rego.v1

threshold := 3

default trip := false

trip if {
	input.consecutive_qa_failures >= threshold
}
