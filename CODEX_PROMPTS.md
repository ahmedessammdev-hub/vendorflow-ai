# Codex prompts — VendorFlow AI

## Before you start

1. Unzip this folder, then in PowerShell: `cd vendorflow-ai; git init; git add .; git commit -m "docs: spec, addendum, architecture, agent rules"`.
2. Open the folder in Codex. Keep the default workspace-write sandbox with approval on request. Allow network access for `uv` and `npm` installs when asked.
3. Send **one prompt per phase**, each in a fresh thread. Read the diff and the phase report before sending the next one. If a gate fails, reply in the same thread with the failure; do not move on.
4. Copy `.env.example` to `.env` after Phase 0. Leave it empty for now; simulation and "AI Unavailable" must work with no keys.

---

## Phase 0 — Bootstrap

```text
Read AGENTS.md, then docs/spec.md, docs/spec-addendum.md, docs/architecture.md, docs/folder-plan.md and docs/metrics-plan.md in full. The addendum overrides the spec.

Do Phase 0 only:
1. Run `git status`, `node -v`, `npm -v`, `uv --version`. Choose the Angular major with the rule in spec-addendum §1. If Node is too old, stop and tell me.
2. Create the folder layout from docs/folder-plan.md. Backend: uv project on Python 3.12 with the stack from addendum §2, ruff, mypy, pytest configured, `GET /api/health` returning LLM mode and Jira mode with no secrets. Frontend: Angular workspace with standalone components, Angular Material, ESLint, an empty dashboard page with the three-part mode banner, and the `gen:api` script.
3. Write .env.example, .gitignore, README skeleton, the four ADR files, docs/limitations.md, and .github/workflows/ci.yml for windows-latest.
4. Start docs/implementation-log.md with the resolved tool and package versions.

Gate: ruff, mypy, `uv run pytest -q` and `npm run build` all exit 0; the health endpoint answers; the Angular page loads and shows the banner. Show me the commands and exit codes. Commit as `phase-0: bootstrap`.
```

## Phase 1 — Domain, persistence, API

```text
Read AGENTS.md. Do Phase 1 only.

Build: enums, Pydantic models, domain/rules.py (completeness checklist and risk rubric exactly as in spec §3), domain/transitions.py (the transition table from docs/architecture.md), SQLAlchemy tables with every constraint in the data model table, Alembic migration, SQLite settings from addendum §6, repositories with compare-and-set and audit append in the same transaction, the request CRUD and audit endpoints, the body-size and field-length limits, scripts/seed_demo.py with the three fixture vendors.

Do not add LangGraph, LLM or Jira code yet. Submit may stop at UNDER_REVIEW for now.

Tests: VF-01, VF-02, VF-03 (high + sensitive + cloud = 6), every illegal transition rejected, version conflict returns 409, persistence across a new engine, XSS string stored and returned as plain text, sockets blocked.

Gate: all checks exit 0; coverage of app/domain ≥ 95 %. Report test counts and coverage. Log and commit as `phase-1: domain, persistence, api`.
```

## Phase 2 — Review graph and human pause

```text
Read AGENTS.md. Do Phase 2 only. Before coding, open the current LangGraph interrupts documentation linked in the addendum and follow the API it shows for the installed version.

Build: the graph in docs/architecture.md with the SQLite checkpointer in checkpoints.sqlite and thread_id = request id; the LLM adapter and rules from addendum §3 including the grounding check, ai_status and the LlmCall table; async submit from addendum §4; the decision endpoint from addendum §5 up to and including the JiraOperation(PENDING) row, with no dispatcher yet; services/recovery.py for requests stuck UNDER_REVIEW and for decisions committed but not resumed.

Tests with a fake LLM fixture: VF-04 (valid output, malformed JSON, fake cited field, provider down), VF-05 (zero create calls at AWAITING_APPROVAL; reject and request-changes create no operation), VF-06 (pause, dispose the app, build a new app on the same files, resume), node replay causes no duplicate rows, prompt-injection case from addendum §10, 50 concurrent approves produce one decision and one operation row.

Gate: all checks exit 0. Then tell me exactly which env vars to set for one live LLM run, and wait. If I provide a key, run one live submit and record model, latency and tokens in the log; if not, record it as SKIPPED. Commit as `phase-2: review graph with durable interrupt`.
```

## Phase 3 — Jira outbox

```text
Read AGENTS.md. Do Phase 3 only. Before coding, check the Jira Cloud REST v3 pages for create issue, create metadata and POST /search/jql, and note in the log anything that differs from addendum §5.

Build: JiraClient interface; simulation client with SIM- keys and a test-only fault switch; live client (basic auth with email + API token from .env, base URL restricted to *.atlassian.net, ADF description builder, label marker, create-metadata preflight, Retry-After handling); the dispatcher and reconciliation exactly as addendum §5; the reconcile endpoint with the audited "I checked Jira" confirmation; startup rule IN_FLIGHT → UNCERTAIN.

Tests with respx only, never a real site: VF-07, VF-09, and one test per row of the result table (201, 400, 401, 403, 404, 429 with Retry-After, connect error, read timeout, reset, 500), search finds the issue on the third poll, search never finds it → UNCERTAIN, crash while IN_FLIGHT, ADF shape, no token in any log line or API response (VF-10). Add the Hypothesis state-machine test from addendum §10.

Gate: all checks exit 0; the create-call counter across the whole suite is 0 before approval. Do not call live Jira in this phase. Commit as `phase-3: jira outbox and reconciliation`.
```

## Phase 4 — Frontend

```text
Read AGENTS.md. Do Phase 4 only.

Build the screens in spec §4 "Frontend UX" plus addendum §8: dashboard with counts from the API, 3-step request form with live evidence checklist, request detail with risk factors in text, AI summary with ai_status and model name, audit timeline, Jira panel (Simulated / link for live / Needs reconciliation with the confirm checkbox), review queue with mandatory reason, persona switcher with the permanent no-authentication banner, polling with timeout, 409 handling that reloads the request, the Metrics page and GET /api/metrics.

Use generated API types only. Keyboard-operable forms, visible focus, labels on every input, loading skeletons, empty states, error messages that say what to do next. No success message before the server confirms.

Tests: unit tests for the form validation and the status and risk components; Playwright journey 1 (Cedar: create → submit → approve → SIM issue → approve again shows no duplicate → reload persists) and journey 2 (Northstar: missing evidence → NEEDS_CHANGES → fix → review → reject → no Jira); axe scan on the four pages; Playwright saves real screenshots to docs/screenshots/.

Gate: lint, unit tests, build and both journeys exit 0; zero serious or critical axe findings. Commit as `phase-4: frontend and e2e`.
```

## Phase 5 — Metrics, hardening, report

```text
Read AGENTS.md and docs/metrics-plan.md. Do Phase 5 only.

1. Write sample_data/eval/golden.jsonl (20 synthetic cases with expected label and reason, 3 of them adversarial), scripts/run_llm_eval.py, scripts/load_test.py (latency plus --race 50), scripts/verify_workflow.py, scripts/collect_metrics.py.
2. Run collect_metrics.py and generate docs/metrics.md in the format given. Anything that needs a live provider and has none is NOT MEASURED with the reason.
3. Write docs/test-report.md (one row per VF-ID: test names, result, evidence), docs/demo-script.md, docs/workflows.md, finish docs/limitations.md and the README (setup from a clean clone, demo steps, screenshots, metrics table inserted by the script, honest limits).
4. Clone the repo into a temp folder and follow the README exactly. Fix whatever breaks.

Gate: every command in AGENTS.md exits 0 in the clean clone. Final report must contain: VF checklist, exact commands with exit codes, LLM mode and Jira mode used, every metric with its value and target, all defects and skipped items. If something does not work, say so. Commit as `phase-5: metrics and report`.
```

---

## Live test (after Phase 5, you run this with Codex)

Put real values in `.env` first. Never paste keys into the chat.

```powershell
# LLM — any OpenAI-compatible provider
LLM_API_KEY=...
LLM_BASE_URL=...
LLM_MODEL=...

# Jira — a free Atlassian Cloud site with a throwaway project
JIRA_MODE=live
JIRA_BASE_URL=https://<your-site>.atlassian.net
JIRA_PROJECT_KEY=VFDEMO
JIRA_ISSUE_TYPE=Task
JIRA_EMAIL=...
JIRA_API_TOKEN=...
```

```text
Read AGENTS.md. My .env now has live LLM and live Jira values for my own test project. I authorize: one LLM eval run on the golden set, and exactly ONE live Jira issue.

1. Start both servers. Run scripts/verify_workflow.py. It must create one issue, print the key, fetch it back and confirm the label and ADF description, then call approve again and confirm no second issue exists by searching the label.
2. Run scripts/run_llm_eval.py, then scripts/collect_metrics.py.
3. Update docs/metrics.md, docs/test-report.md (VF-08 with the real key) and the README table.

Stop and ask me if anything would create more than one issue. Report the real numbers, including the ones that miss their target.
```

## If a phase goes wrong

```text
Stop. Do not change tests to make them pass. Show me: the failing command, the full error, the files you changed since the last commit, and your best hypothesis. Then propose the smallest fix and wait.
```

When Codex repeats a mistake, ask it for the cause and add one specific line to AGENTS.md so the next thread starts with that knowledge.
