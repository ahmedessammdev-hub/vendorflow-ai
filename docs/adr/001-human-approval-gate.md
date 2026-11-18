# Human approval before Jira

Accepted design. The requester supplies evidence and the model drafts advice. A reviewer owns the decision and gives a reason. Persist the approval, audit event and pending operation in one transaction before dispatch. Reject and request-changes paths create no Jira operation. This adds a review step and provides an auditable authorization boundary.
