# VendorFlow AI — Multi-Agent Vendor Operations
## Standalone Codex implementation brief | Interview-Ready Portfolio MVP

> **CODEX EXECUTION MANDATE:** Actually implement, run, test, demonstrate and document the application in this document—not another plan. Inspect all existing files, git history/status and README before changing a pre-existing repository. Work in verified stages, commit meaningful milestones, and log real test outcomes. **Never execute a supplier approval or create a live Jira issue without explicit reviewer action.** Do not misrepresent fixture/Mock Jira integrations as live. Propose and justify any material change to the agreed workflow/demo scope before implementing it. Never invent test results, live vendor integrations or AI capability.

## 0. Context, scope and environment

- **Product:** VendorFlow AI, a portfolio-scale **agent-assisted** vendor onboarding and procurement review tool for enterprise operations teams.
- **Business fit:** Vendor management, third-party risk and workflow automation—common enterprise AI use cases. This is a **personal synthetic demo**, not a clone or derivative of an employer's private system. Do not reuse employer proprietary code, schemas, regulations, customer data, or internal screenshots.
- **User:** Procurement requester and review officer. Users submit supplier details and a small set of evidence artifacts; the system checks completeness, calculates a transparent **illustrative** risk score, drafts an AI summary/recommendation, requests human signoff, and optionally creates a Jira issue after authorization.
- **Environment:** Windows 11 PowerShell; Python 3.12 managed with `uv`, no Docker; Node.js preferably >=20.19.0. Angular **21 LTS** is compatible with Node 20.19+; Angular 22 requires newer Node, so do not silently force Angular 22 on the user's setup. Use an Angular version compatible with the actual installed Node, confirm via official compatibility table.
- **Target:** A focused working interview demo with persistence, idempotency, real/tested agent orchestration and a visible audit trail—not a production compliance engine. Demo must run without real Jira credentials in clearly labeled **Simulation Mode**; live Jira is optional but supported.
- **LLM:** Configurable external OpenAI-compatible provider for actual summarization and recommendation. If no API access, explicit `AI Unavailable` state or clearly labeled test fixture; never substitute fictitious live intelligence.

## 1. Demo narrative and interview problem

**Problem:** Onboarding new suppliers is fragmented between requesters, compliance reviewers, document requests and issue trackers. Information is incomplete; AI can accelerate evidence summarization but must not decide authorization.

**Complete 3-minute happy-path journey:**
1. Open a dashboard of seeded **synthetic** supplier requests. Click **New Request**.
2. Enter `Cedar Cloud Services` (synthetic), cloud-hosting service, criticality `high`, sensitive-data access `yes`, attach/select mock evidence. Submit.
3. See deterministic completeness checks and a score with **visible factors**; AI produces a concise evidence-based recommendation. It does not claim CBE/regulatory compliance.
4. Open review queue; the request is **Awaiting Human Review**. Explicit reviewer Approve/Reject/Request Changes choices, with reason, are required.
5. Approve: system records immutable-style audit event, then creates a Jira issue **only if live integration is configured**; otherwise a plainly labeled simulated issue (e.g. `SIM-...`).
6. Refresh/restart and confirm state persists; intentionally click approve twice and show **no duplicate issue**. Alternatively demo a missing-document case that is returned for corrections rather than advanced.

**Skills demonstrated:** bounded LLM tools, LangGraph state and human-in-the-loop interrupts, deterministic business rules, integration design, REST/API contracts, retries/idempotency, security boundaries, Angular/FastAPI, automated testing, observability and enterprise workflows.

### Most important technical story

> **AI can summarize and recommend, but authorization and external side effects are controlled by a deterministic state machine and human decision.** Explain checkpoints, resumability, auditable reasons, and duplicate Jira issue prevention, especially after an ambiguous network timeout.

## 2. Feature review and scope decisions

| Original proposal | Decision | User value / technical evidence / relative effort | Rationale |
|---|---|---|---|
| Vendor onboarding form and validation | **KEEP** | High / medium / low | The concrete entry point and business context. |
| Multiple AI agents | **MODIFY** | Medium / very high / medium | Use 2 bounded, purposeful AI-assisted stages + deterministic tools; no arbitrary swarms or fabricated autonomy. |
| Risk scoring | **KEEP, SIMPLIFY** | High / high / low | Transparent demo-only rules, never legal/real credit ratings. |
| Human approval | **KEEP, NON-NEGOTIABLE** | Very high / very high / medium | Must gate all external writes and decisions. |
| Jira issue creation | **KEEP WITH ADAPTER** | High / high / medium | Real Jira Cloud adapter plus explicit simulation; only after approval. |
| Full ERP, procurement and financial integrations | **DEFER** | Medium / medium / high | Hard to test and unsafe to pretend a live enterprise environment exists. |
| Multi-tenant RBAC / SSO | **DEFER** | High in prod / medium / high | Demo roles are UI personas, **not authentication**. Document the limitation. |
| Audit history and persistence | **ADD** | Very high / very high / medium | Demonstrates controls and recovery. |
| Workflow unit tests and integration fault injection | **ADD** | High / very high / medium | Essential differentiator vs a scripted AI demo. |
| Regulatory-compliance decision automation | **EXCLUDE** | Unsafe / misleading / high | Demo scoring is explicitly not authoritative or a replacement for review. |

**Locked MVP:** Request intake; required-field/document validation; 2 AI-assisted stages; deterministic score with factors; submit/return/review/approve/reject; LangGraph interrupt + persistent state; Jira issue in configured live or clearly labeled mock mode; event log; 2 scenarios + one failure. No external vendor verification, actual regulatory decisions, bank system connections or unauthorized access.

## 3. Detailed workflow and business rules

### Actors and states

- `Requester`: creates and updates drafts or returned requests.
- `Reviewer`: views evidence and decides Approve, Reject or Request Changes. **MVP persona switcher is not security**. Place a persistent “Demo mode: no authentication” warning; production access control is deferred.
- Canonical states: `DRAFT`, `NEEDS_CHANGES`, `SUBMITTED`, `UNDER_REVIEW`, `AWAITING_APPROVAL`, `APPROVED`, `REJECTED`, `JIRA_PENDING`, `JIRA_CREATED`, `JIRA_FAILED`. Final approved status should remain explicit even when Jira fails; do not change business approval to rejected due to transport errors.
- Allowed transitions: `DRAFT -> SUBMITTED`; `SUBMITTED -> NEEDS_CHANGES | UNDER_REVIEW`; `NEEDS_CHANGES -> SUBMITTED`; `UNDER_REVIEW -> AWAITING_APPROVAL | NEEDS_CHANGES`; `AWAITING_APPROVAL -> APPROVED | REJECTED | NEEDS_CHANGES`; `APPROVED -> JIRA_PENDING` when integration requested; `JIRA_PENDING -> JIRA_CREATED | JIRA_FAILED`; retry `JIRA_FAILED -> JIRA_PENDING` only under safe dedupe/reconciliation conditions. Rejection final for demo; edit and resubmit requires a *new* request unless explicitly designed otherwise.

### Required fields & evidence

- `vendor_name` 2–120 chars; `service_category` `cloud_hosting|software|consulting`; `business_criticality` `low|medium|high`; `sensitive_data_access` boolean; `requester_department` non-empty; `service_description` non-empty.
- Required evidence checklist is category-dependent **synthetic data**, stored as metadata flags for fast MVP: `business_registration`, `security_questionnaire` for cloud/software, `service_sla` for high criticality. Attach small mock PDF/text evidence optionally; **a checked box is not independent document verification**.
- Missing/invalid fields -> 422 with field errors. Missing required evidence -> `NEEDS_CHANGES` with exact missing list and correction option; **do not send to approval**.
- Never allow an LLM to override completeness conditions.

### Demonstration risk rubric (not regulatory)

Example, deterministic with `risk_score` and `risk_factors`:
- High criticality +3; medium +1; low +0.
- Sensitive data access +2.
- Cloud hosting category +1.
- Score 0–1 `LOW`, 2–3 `MEDIUM`, 4+ `HIGH`.
- Missing required evidence **blocks review** rather than being compensated by a low score.

Explain that scores represent a sample internal prioritization rubric only and are not applicable to a real institution without expert validation. Do not infer risk from nationality, ethnicity or other sensitive traits.

### Agent orchestration — genuinely bounded

```text
POST /requests/{id}/submit
  -> Deterministic validation + evidence completeness
  -> Under Review
  -> LangGraph: Intake Summary Node (LLM, strict schema)
  -> LangGraph: Risk Factors Tool (deterministic)
  -> LangGraph: Review Recommendation Node (LLM with bounded tool results)
  -> PERSIST checkpoint + interrupt() before approval
  -> Awaiting Human Approval in UI
  -> Reviewer action + reason via resume Command
  -> state machine decision (not AI decision)
      -> Approved -> Jira Adapter (simulation or live)
      -> Rejected / Needs Changes -> no Jira write
  -> durable event log and final state
```

Use purposeful AI outputs: `IntakeSummary {what_is_requested, service_description, evidence_summary, missing_information}` and `Recommendation {recommendation: approve_review|request_more_info|escalate, justification, cited_input_fields, caution}`. Explain that `recommendation` is **advice** only, not a state change. Tools `get_request`, `list_evidence`, `compute_demo_risk` have typed inputs/outputs. Guard against tool-call loops and invalid output with limits, schema parsing, and fallback to `review_required` (do not auto approve).

### Human-in-the-loop and retry correctness

- LangGraph interruption happens **before** any irreversible action. Configure a stable `thread_id = request UUID` and durable SQLite checkpointer using a supported package/version; persist business data and graph checkpoints separately, ideally same local SQLite file with clearly named tables.
- `interrupt()` resumes by using `Command(resume=...)` with thread configuration. Beware that interrupted nodes may rerun on resume. Do not perform external side effects in nodes that may replay before the interrupt.
- Approval endpoint must validate expected state/version (optimistic concurrency or atomic compare-and-set); second concurrent approval returns stable existing decision, or explicit conflict—not a second Jira write.
- Add an outbound `JiraOperation {request_id unique, status, issue_key?, attempt_count, last_error, last_checked_at}`. Create one operation per approved request.
- **Ambiguous timeout is not permission for blind retry**: reconcile by unique `VendorFlow Request ID` marker (e.g. Jira issue property or description plus targeted search) before another create attempt. If uncertain, show `Needs reconciliation` and require safe manual review; do not promise at-most-once across a network with no server-side idempotency guarantee.

## 4. Architecture and stack

- **Frontend:** Angular **21 LTS** with standalone components, typed reactive forms, router, signals/RxJS as suitable. Good for enterprise workflow forms and aligned with existing Angular experience. Confirm local Node >=20.19 before creating the app; otherwise document update steps rather than silently breaking the environment.
- **Backend:** Python 3.12 + FastAPI + Pydantic + SQLAlchemy/SQLModel + SQLite for local persistence + `uv` for all Python environment management.
- **Agent graph:** LangGraph with SQLite-backed checkpointing (`langgraph-checkpoint-sqlite` where compatible). Explicit durable thread per request; separate pure functions for validations/risk.
- **LLM integration:** OpenAI-compatible configurable adapter (`LLM_API_KEY`, `LLM_BASE_URL`, `LLM_MODEL`); fake provider only in automated tests with clear labels. Disable agent processing with actionable message if live mode lacks a key.
- **Jira integration:** Atlassian **Jira Cloud REST API v3**. Use configured base URL, project key and issue type. For a local-only demo allow email + API token through environment for personal scripts, but document that OAuth/Forge is preferred for real distributed apps. Do **not** accept arbitrary user-provided Jira host URLs. Issue `description` uses Atlassian Document Format (ADF), not a plain string in API v3.
- **Testing:** Pytest + HTTPX `TestClient`, mocked LLM/Jira service in unit/integration tests; Angular `npm test` and `npm run build`. Browser E2E via Playwright only if feasible after core gates.
- **No Docker required.** SQLite is a deliberate demo simplification; Postgres + managed queue is the documented future production alternative.

### Proposed repository layout

```text
vendorflow-ai/
  README.md
  .env.example
  .gitignore
  docs/{architecture.md,workflows.md,adr-001-human-approval.md,test-report.md,demo-script.md,limitations.md,implementation-log.md}
  backend/
    pyproject.toml
    uv.lock
    app/
      main.py
      api/{requests.py,review.py,jira.py,audit.py,health.py}
      domain/{models.py,enums.py,rules.py,transitions.py}
      agents/{graph.py,nodes.py,schemas.py,tools.py,llm_adapter.py}
      integration/{jira_client.py,jira_mock.py,operation_store.py}
      persistence/{database.py,repositories.py,checkpointer.py}
      core/{config.py,security.py}
    tests/{unit,integration,fixtures}/
  frontend/
    angular.json
    package.json
    src/app/{core,features,shared}/
  sample_data/{requests.json,evidence/}
  scripts/{seed_demo.py,verify_workflow.py}
```

### Core data model

- `VendorRequest`: `id`, vendor/service fields, criticality, sensitive_data_access, department, `status`, `version`, `created_at`, `updated_at`.
- `Evidence`: `id`, `request_id`, `kind`, `present`, optional synthetic attachment pointer. Validate allowed kinds; never claim verification of unchecked attachments.
- `Assessment`: `request_id`, `score`, `band`, `factors_json`, `agent_summary_json`, `recommendation_json`, `model_name`, `created_at`.
- `ReviewDecision`: `request_id`, `reviewer_label`, `action`, `reason`, `created_at`; one decision per approval step/version.
- `JiraOperation`: unique `request_id`, `mode`, `status`, `issue_key`, `external_marker`, `attempts`, `last_error`.
- `AuditEvent`: `id`, `request_id`, `actor_type`, `event_type`, `from_status`, `to_status`, timestamp, structured detail (no credentials). Append-only via application API.

### Endpoint contract

| Route | Purpose |
|---|---|
| `GET /api/health` | LLM and Jira mode flags; do not expose credentials. |
| `GET /api/requests` | Dashboard list, status filters, counts computed from DB. |
| `POST /api/requests` | Create DRAFT with typed validation. |
| `GET /api/requests/{id}` | Request, evidence, risk factors, recommendation, review status. |
| `PATCH /api/requests/{id}` | Edit DRAFT / NEEDS_CHANGES only. |
| `POST /api/requests/{id}/submit` | Validate; process graph; return NEEDS_CHANGES or AWAITING_APPROVAL. |
| `POST /api/requests/{id}/decision` | `approve|reject|request_changes`, reviewer label, reason, expected version. Resume graph only when legal transition. |
| `POST /api/requests/{id}/jira/reconcile` | Reviewer-triggered safe retry/reconcile of failed/uncertain Jira operation. |
| `GET /api/requests/{id}/audit` | Chronological event list. |
| `GET /api/settings/integrations` | Jira `disabled|simulated|live`, LLM mode, no secrets. |

### Frontend UX

- **Dashboard:** requests, status pills, category and risk, count cards from actual database, “New request”; empty and loading states.
- **New/Edit request:** 3-step form (Vendor / Service & Risk / Evidence), required-field validation and live checklist. No fake upload analysis.
- **Request detail:** request facts; colored risk band **plus reasons in text**; AI summary with model status; audit timeline.
- **Review queue:** Awaiting Approval, evidence summary, clear AI disclaimer, explicit `Approve`, `Request Changes`, `Reject` actions with mandatory reason. Show demo-only persona warning.
- **Jira status:** link only for real issues verified from configured site; `SIM-...` displays **Simulated**, never a forged Jira link. Show failed, pending and reconciliation states.
- Responsive, accessible keyboard forms, skeletons, error toast with retry instructions and no celebratory “Success” until server confirms.

## 5. Feature acceptance criteria

| ID | Test | Required observation |
|---|---|---|
| VF-01 | Request form | Valid draft persists across refresh/restart; invalid required fields fail with accurate messages. |
| VF-02 | Completeness | Missing SLA on high-criticality request -> NEEDS_CHANGES with exact missing evidence; no review and no Jira. |
| VF-03 | Transparent risk | Deterministic inputs produce exact documented score and factors (test high-criticality + sensitive access + cloud = 6). |
| VF-04 | AI evidence | With configured provider, get schema-valid summary/recommendation grounded only in request fields, with model attribution; invalid model output blocks or flags review, never auto approves. |
| VF-05 | Human gate | At AWAITING_APPROVAL, there is **zero** Jira create operation. Reject/Request Changes never creates Jira issue. |
| VF-06 | Approval persistence | Reviewer approval records reason, audit event and checkpoint; survives process restart and resumes correctly. |
| VF-07 | Jira mock | Approved demo request creates exactly one **labeled simulated** issue and records `SIM-...`. |
| VF-08 | Jira live | If configured, one approved request creates one Jira Cloud issue in user's *own test project* with correct ADF description and traceable marker; link resolvable. If not configured, mark test SKIPPED. |
| VF-09 | Retry/concurrency | Repeated/concurrent approval yields at most one stored operation; ambiguous Jira timeout follows reconciliation path, no unsafe blind duplicate POST. |
| VF-10 | Audit/security | All important transitions logged; cannot edit approved request or approve from unauthorized state; tokens absent from logs/API. |
| VF-11 | Build/QA | Backend tests and Angular build pass; README runbook works. |

## 6. Phased build with verification gates

### Phase 0 — Inspect repo and bootstrap

- Inspect existing code and git state; identify working pieces before overwriting anything.
- Record version decisions (`node -v`, `uv --version`, `python` via `uv`). Generate backend + Angular 21 compatible workspace.
- Create scope, `.env.example`, ADR, initial README, empty state view and FastAPI health endpoint.
- **Gate:** `uv run pytest -q` baseline and `npm run build` pass; health endpoint and Angular page load. Commit.

### Phase 1 — Models, validation, scoring, API

- Create SQLite schema/migrations (Alembic optional but recommended), typed Pydantic domain models, state transitions, CRUD, audit appends, demo seed requests.
- Implement exact completeness checklist and scoring; only legal state changes allowed.
- **Gate:** automated VF-01, VF-02, VF-03, illegal transitions, data persistence; verify manually via `/docs`. Commit.

### Phase 2 — LangGraph AI and durable human pause

- Add graph with two bounded AI stages and deterministic risk tool. Structured responses, safe error states, durable checkpointer, interrupt prior to approval, resume with `Command(resume=...)`.
- If LLM unavailable, show **AI Unavailable** and keep request in explicit review-required state; do not fake a live completed analysis. Test service with fixture adapter only in tests.
- **Gate:** VF-04, VF-05, VF-06 tested with fixture provider, restart while paused, resume after restart, no double side effects. If real provider configured, run and record one live evaluation. Commit.

### Phase 3 — Jira adapter

- Create `JiraClient` interface with real and simulated implementations; ADF description, known project, unique external request marker, operation tracking and duplicate-defense logic.
- Implement tests injecting 401, 429, 500, timeouts and ambiguous responses; **no blind retry after create-timeout**.
- **Gate:** VF-07, VF-09 automated; VF-08 manually only if credentials supplied. Never accidentally create Jira issues during tests. Commit.

### Phase 4 — UX and integrated demo

- Implement Dashboard, Request Form, Detail, Review Queue and Audit Timeline. Show demo-mode/auth warning and integration mode visibly.
- **Gate:** complete two journeys in browser: valid request approved -> simulated/live Jira; incomplete request -> needs changes -> correction -> review. `npm run build` passes and all states show useful errors. Commit.

### Phase 5 — Hardening, tests, deliverables

- Exercise replay race, invalid transitions, power/restart while waiting, provider failure, Jira duplicates, unsupported evidence, log sanitization. Produce honest test report and full architecture.
- **Gate:** full backend test suite, frontend build and smoke run; README tested from clean clone; commit final. Report actual outcomes, including skipped live integration.

**PowerShell commands (verify exact generated locations and dependencies):**

```powershell
cd backend
uv sync
uv run uvicorn app.main:app --reload --port 8000
# second terminal
cd frontend
npm ci
npm start
# quality gates
cd backend; uv run pytest -q
cd frontend; npm run build
```

`JIRA_MODE=simulation` is default; live Jira requires `JIRA_BASE_URL`, `JIRA_PROJECT_KEY`, `JIRA_EMAIL`, `JIRA_API_TOKEN` and an appropriate issue type / create permission. API token is stored server-side in `.env`, never frontend code. Add an explicit verification step of issue-create metadata or configurable issue type; do not assume all sites use the same naming.

## 7. QA fixtures, error cases, evidence, documentation

**Synthetic fixture requests:**

1. `Cedar Cloud Services`: high criticality, sensitive-data access, cloud hosting; all required evidence supplied -> score 6 -> awaiting approval -> approve -> simulated Jira issue.
2. `Northstar Advisory`: low criticality, no sensitive access, consulting service; incomplete registration -> NEEDS_CHANGES -> attach evidence -> review -> reject (no Jira).
3. `River Apps`: medium, software; missing security questionnaire -> needs changes; after correction, provider returns malformed JSON -> safe review failure, **no Jira**.

**Test matrix:** pure score tests, required-document matrix, request version conflict, graph checkpoint persistence, interrupted-node replay, double-click approve, duplicate Jira response, ambiguity after timeout, Jira 401/429, LLM schema failure, malformed input, XSS in vendor name rendered as text, log credential redaction, no side effects on rejection.

**Required repo artifacts:** `README.md` setup and demo, `.env.example`, `docs/architecture.md` graph and state diagram, `docs/adr-001-human-approval.md`, `docs/workflows.md`, `docs/test-report.md` actual tests, `docs/demo-script.md`, `docs/limitations.md`, `docs/implementation-log.md`, 2+ genuine screenshots, seed data and reproducible tests. Provide one GitHub-ready README hero screenshot (optional), but never claim real enterprise adoption.

**Risk note:** LLM recommendations are not binding decisions. Demonstration risk score is *not* a compliance risk assessment. Persona switching is *not* authorization and is not safe for an internet-exposed deployment. Only synthetic data should be processed.

## 8. Interview script: ~3 minutes

- **0:00–0:30:** Show dashboard; describe the bottleneck in vendor onboarding and explain AI augments review, does not approve vendors.
- **0:30–1:10:** Fill/seed a high-criticality request; show required evidence and **transparent risk factor score**.
- **1:10–1:40:** Show AI recommendation and LangGraph `interrupt`-paused state; inspect the workflow diagram.
- **1:40–2:15:** Reviewer explicitly approves with reason; show Jira **Simulated** or verified actual link, plus audit timeline and persistent status.
- **2:15–2:40:** Repeat approval or show missing document to demonstrate state guards and idempotency.
- **2:40–3:00:** Show tests for no pre-approval Jira calls and concurrency; describe how a Postgres/outbox/OAuth architecture would replace SQLite/demo persona in production.

### Engineering trade-offs to defend

1. **LLM vs deterministic logic:** LLM summarizes and suggests; required fields, approval and risk rubric are rule-based, inspectable and tested.
2. **LangGraph vs simple function chain:** checkpoints and interruptions are justified by multi-step review and resume-after-restart, not for hype.
3. **SQLite vs Postgres:** easy zero-Docker demo, but limited concurrency and multi-node support.
4. **Jira integration:** API v3 ADF descriptions, credential handling, side-effect reconciliation and explicit simulation labeling.
5. **Production controls:** real authentication/RBAC, audit immutability, secret storage, queue/outbox, monitoring and governance are not solved in this MVP.

## 9. Official implementation references

- LangGraph interrupts and checkpoints: https://docs.langchain.com/oss/python/langgraph/interrupts
- Jira Cloud REST API v3: https://developer.atlassian.com/cloud/jira/platform/rest/v3/
- Jira issue creation / ADF: https://developer.atlassian.com/cloud/jira/platform/rest/v3/api-group-issues/
- Jira Cloud basic auth for local scripts: https://developer.atlassian.com/cloud/jira/platform/basic-auth-for-rest-apis/
- Angular / Node.js compatibility: https://angular.dev/reference/versions
- FastAPI testing: https://fastapi.tiangolo.com/tutorial/testing/

**Codex final report MUST include:** VF-ID feature checklist; exact commands with real exit codes; LLM mode and Jira mode (live vs simulation); reproducible screenshot/demo path; all defects and skipped tests; all meaningful implementation decisions and actual external Jira issue key **only if it exists**. If any feature does not work, state it rather than glossing over it.
