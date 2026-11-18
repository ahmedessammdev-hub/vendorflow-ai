# Jira delivery through an outbox

Accepted design. Store one operation per request under a database uniqueness constraint. A dispatcher claims it after commit. Record a unique request marker in the issue and search for it after an ambiguous failure. An inconclusive search leaves the operation uncertain until reconciliation. The extra storage and recovery code preserve the approval and account for Jira search indexing delays.
