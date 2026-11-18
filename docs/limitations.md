# Demo boundaries

VendorFlow demonstrates an end-to-end local onboarding review using synthetic supplier data. Requester and Reviewer are personas with no authentication. Use a single API worker bound to loopback. Keep the business and checkpoint databases together when moving the workspace.

The illustrative risk rubric prioritizes review. Evidence records are declarations. The application does not verify documents or make regulatory compliance decisions. AI output is advisory. Citation validation checks named fields and values. A human still evaluates the interpretation. An unavailable provider or invalid response leaves the request available for review with the failure visible.

The hosted inference deadline is configurable. Missing token usage and missing prices are reported as unmeasured. Auto-routing gateways may choose different underlying providers across calls. Synthetic golden-set agreement is a small sanity check. See the current [measurements](metrics.md).

Simulation persists real local rows through the same dispatcher as live mode. Historical mock and browser results establish behavior under controlled conditions. A real Jira issue has not been created in this project verification. Live search is eventually consistent. Manual confirmation after an inconclusive search can still result in a duplicate if the reviewer overlooks an existing issue.

Local ASGI performance measurements exclude external network transit and include background tasks. Browser automation covers two workflows in Edge and axe scans selected rendered states. Hosted CI and production deployment are separate from these local results.
