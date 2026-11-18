# Demo boundaries

This release exposes local health and integration configuration plus an Angular dashboard shell. Request intake, evidence, risk, AI review and Jira dispatch belong to later phases.

The dashboard uses synthetic data only. Demo personas provide no access control. Bind the API to loopback and keep the dashboard on the same machine.

Integration modes describe settings. Phase 0 does not probe either provider. The expected evidence will be declarations by the requester, and the sample risk rubric is illustrative. Independent document verification and compliance decisions are outside the demo.

A future live Jira create can have an ambiguous outcome. The design records uncertainty and searches for a request marker before any further create attempt. See [the architecture](architecture.md).
