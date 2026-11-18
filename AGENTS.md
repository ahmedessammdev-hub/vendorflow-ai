# AGENTS.md — VendorFlow AI

Agent-assisted vendor onboarding review. A requester submits a supplier request, deterministic rules check completeness and compute a demo risk score, an LLM drafts a summary and a recommendation, a human reviewer decides, and only then a Jira issue is created (simulated by default). Portfolio demo with synthetic data only.

## Read before any work

1. `docs/spec.md` — the product spec and acceptance criteria (VF-01 … VF-11).
2. `docs/spec-addendum.md` — approved changes. **Where it conflicts with the spec, the addendum wins.**
3. `docs/architecture.md` — components, state machine, graph, Jira outbox.
4. `docs/folder-plan.md` — where every file goes.
5. `docs/metrics-plan.md` — the numbers to collect and how.

Work one phase at a time (phases are in `CODEX_PROMPTS.md`). Do not start a phase until the previous gate passed.

## Invariants (a change that breaks one of these is wrong, even if tests pass)

- **I1** No Jira create call, live or simulated, before a persisted human `approve` decision.
- **I2** At most one `JiraOperation` per request, enforced by a DB UNIQUE constraint. Never re-POST after an ambiguous failure without reconciliation.
- **I3** LLM output never changes a request status. Only `backend/app/domain/transitions.py` does.
- **I4** Completeness and risk scoring are pure deterministic functions. The LLM cannot override them.
- **I5** Simulation is always labeled. `SIM-…` keys are never rendered as links.
- **I6** No secrets in logs, API responses, audit events, frontend code, test fixtures or git history.
- **I7** `AuditEvent` rows are append-only. No update or delete path exists in the code.
- **I8** Never invent results. Every number in `docs/` comes from the output of a script or test run in this repo, with the command and commit SHA beside it.

## Environment

- Windows 11, PowerShell. No Docker, no WSL, no bash-only syntax. Chain commands with `;` and check `$LASTEXITCODE`.
- Python 3.12 through `uv` only. Never `pip install` outside `uv`.
- Run `node -v` first. Pick the Angular major from the rule in `docs/spec-addendum.md` §1. Never upgrade Node yourself; if it is too old, stop and tell the user.
- The backend binds to `127.0.0.1` only.

## Commands

```powershell
# backend (run from backend/)
uv sync
uv run ruff check . ; uv run ruff format --check .
uv run mypy app
uv run pytest -q
uv run pytest --cov=app --cov-report=term-missing
uv run uvicorn app.main:app --port 8000

# frontend (run from frontend/)
npm ci
npm run gen:api        # regenerate TS types from the backend OpenAPI schema
npm run lint
npm test -- --watch=false
npm run build
npx playwright test    # e2e, needs both servers running

# repo root
uv run --project backend python scripts/seed_demo.py
uv run --project backend python scripts/verify_workflow.py     # live smoke, prints PASS/FAIL per VF-ID
uv run --project backend python scripts/collect_metrics.py     # writes docs/metrics.md
```

If a command here stops working, fix this file in the same commit.

## Code rules

- Layering: `api` → `services` → `domain` + `persistence` + `integration` + `agents`. `domain/` imports nothing from FastAPI, SQLAlchemy, LangGraph or httpx.
- Every status change goes through `domain.transitions.apply(...)` inside one DB transaction that also writes the `AuditEvent`.
- State-changing endpoints take `expected_version` and use compare-and-set. A stale version returns 409 with the current state.
- All outbound HTTP (LLM, Jira) uses `httpx` with explicit timeouts, behind an interface in `integration/` or `agents/llm_adapter.py`.
- LLM input: vendor-supplied text is untrusted data. Pass it in a delimited data block, never as instructions. LLM nodes get no write-capable tools.
- LLM output: parse with Pydantic. One repair retry at most, then `ai_status = INVALID_OUTPUT`. Never auto-approve.
- Graph nodes before `interrupt()` must be safe to re-run. No external side effects inside the graph at all; Jira goes through the outbox dispatcher.
- Frontend: standalone components, signals, typed reactive forms, generated API types only (no hand-written DTOs). Render all user text with interpolation, never `innerHTML`.
- Type hints everywhere in Python; `strict` TypeScript.

## Test rules

- Tests never touch the network. Use `respx` for httpx and `pytest-socket` to block real sockets. Live checks live only in `scripts/verify_workflow.py` and are opt-in by env var.
- Fake LLM and mock Jira are test fixtures or explicit `simulation` mode. They are never reported as live.
- Each VF-ID has at least one test whose name contains the ID, e.g. `test_vf05_no_jira_before_approval`.
- Do not delete, skip or weaken a failing test to pass a gate. Fix the code, or stop and report.
- Do not chase coverage with assertion-free tests.

## Ask the user before

- Any call to a live Jira site or a paid LLM API.
- Adding a dependency that is not in the stack table (`docs/spec-addendum.md` §2).
- Changing a state, a transition, the risk rubric or an invariant.
- Deleting files you did not create, or rewriting git history.

## Definition of done for a phase

1. Lint, type check, tests and frontend build all exit 0.
2. The phase gate in `CODEX_PROMPTS.md` is demonstrated, not assumed.
3. `docs/implementation-log.md` has a dated entry: what was built, exact commands, exit codes, test counts, decisions, known defects.
4. One commit per milestone with a message like `phase-2: langgraph review graph with durable interrupt`.
5. Final message lists what works, what does not, and what was skipped and why.

## When stuck

Stop after two failed attempts at the same error. Report the command, the full error, what you tried and your best hypothesis. Do not work around a failure by faking, stubbing or hiding it.
