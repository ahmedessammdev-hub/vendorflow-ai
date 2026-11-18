# Review and recovery

## Requester and reviewer

The requester saves a draft, opens its detail page and explicitly submits. The service validates evidence and records a risk breakdown. Incomplete submissions enter NEEDS_CHANGES with the exact missing declarations. Complete submissions enter UNDER_REVIEW. LangGraph runs summary and recommendation stages and checkpoints the interrupt in SQLite.

AWAITING_APPROVAL accepts one review action for the current version. Approve, reject and request changes each require a reviewer label and reason. An outdated version receives HTTP 409. The UI reloads the record so the reviewer can inspect it again.

Approval persists the decision, audit entries and one outbox operation in the same transaction. A single-worker dispatcher sends that operation after commit. Simulated tickets have a SIM key without a link. A false-negative search can happen while Jira indexes a new issue. After an ambiguous delivery the dispatcher polls by unique label. A further create from UNCERTAIN requires an explicit, audited confirmation that the reviewer checked Jira. The review remains approved throughout.

## Local verification

The default smoke starts a real loopback API against a temporary database, submits synthetic fixtures, terminates the server while a request is paused, restarts it, and checks the decision, Jira simulation and audit history. Unit and integration tests block network sockets. Playwright's two local browser journeys run without external integrations.

## Opt-in live checks

Place compatible model settings or Jira test-site settings in the ignored root .env and restart the appropriate API. The model golden set contains hand-labeled synthetic cases. Its expected labels are held outside model input. Run an authorized evaluation with `uv run --project backend python scripts/run_llm_eval.py --live`. An empty or unreachable provider is recorded separately from label quality.

For a live Jira check, a human first reviews one synthetic request waiting for approval, chooses a reason, and explicitly authorizes one issue in their own site. On the same machine, with the API running in live mode, set `$env:VENDORFLOW_LIVE_JIRA='1'`. Run `uv run --project backend python scripts/verify_workflow.py --live-jira <request-uuid> --version <version> --reviewer "<reviewer>" --reason "<reason>" --port 8000`. The script checks the version, sends the decision, fetches the created issue, verifies the request label and ADF description, and replays the stale decision to verify conflict handling. If delivery remains uncertain, inspect the original issue marker before reconciling.
