# Two structured review nodes

Accepted design. LangGraph supplies request context to an intake-summary node and a recommendation node. Deterministic application code computes the score, validates output and controls transitions. A persisted interrupt waits for the reviewer. This bounds cost and makes malformed or unavailable model output a visible, testable state.

The approved evidence improvement for Phase 2 will compare cited structured field values with the request. Phase 5 will compare recommendations against a simple rules baseline on the same synthetic cases.
