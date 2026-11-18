# Three-minute interview walkthrough

[Watch the two-minute captioned walkthrough](demo/vendorflow-demo.mp4). The recording uses the local application with synthetic drafts, a disconnected model and Jira simulation. The live model results are documented in [the case review](model-review.md).

Use synthetic supplier data. Open the local dashboard with Jira in Simulation. The top bar shows the current AI configuration and the demo persona.

| Time | Show | Explain |
|---|---|---|
| 0:00–0:35 | As Requester, open Cedar or create a cloud hosting request with high criticality and sensitive access. Declare registration, security questionnaire and SLA. | The checklist comes directly from the API. Evidence is declared by the requester. |
| 0:35–1:10 | Submit, then open the detail page and read the factors beside the risk band. | Criticality contributes three points, sensitive access two and cloud hosting one. The human still decides. |
| 1:10–1:50 | Inspect AI status, model and citations when available. Switch to Reviewer, open Review queue and enter a reason. | The graph pauses durably. Provider failure is visible, and a missing model result leaves the decision open. |
| 1:50–2:20 | Choose Approve on this synthetic demo request. Inspect the simulated issue, audit reason and timestamps, then refresh. | One operation is stored per request. A lost acknowledgement triggers a marker search before another create can be considered. |
| 2:20–3:00 | Switch back to Requester and open Northstar. Submit the incomplete draft, inspect missing evidence, edit, save and resubmit. | The deterministic checklist blocks incomplete submissions. Reviewers can reject a corrected request without a Jira create. |

[Dashboard](screenshots/dashboard.png) · [Intake](screenshots/request-form.png) · [Queue](screenshots/review-queue.png) · [Completed review](screenshots/request-detail.png) · [Metrics](screenshots/metrics.png)
