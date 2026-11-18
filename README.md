# VendorFlow AI

A local portfolio demo for procurement review using synthetic supplier data. The request API now persists synthetic drafts, checks declared evidence, calculates risk and records the request history. The Angular dashboard currently displays integration modes. The full journey and acceptance criteria are in [the product spec](docs/spec.md) and [approved addendum](docs/spec-addendum.md).

## Run on Windows

Use PowerShell with Node 24.15 or later within the 24.x series, npm, and uv. From this repository root, open two terminals.

**API terminal**

```powershell
Copy-Item .env.example .env -ErrorAction Stop
cd backend
uv sync --locked
uv run uvicorn app.main:app --host 127.0.0.1 --port 8000
```

Copy the environment file only on initial setup. Empty LLM settings and the default Jira simulation mode work offline after dependency installation. Inspect the health response at [localhost](http://127.0.0.1:8000/api/health).

**Dashboard terminal**

```powershell
cd frontend
npm ci
npm start
```

Open [the dashboard](http://localhost:4200). The development server proxies API requests to the local backend. The banner loads its integration modes from the API. Configured mode reports configuration only. If the API goes offline, the banner offers a retry.

If port 8000 is occupied, launch uvicorn with `--port 8426`, then set `$env:VENDORFLOW_API_PORT = "8426"` in the dashboard terminal before running `npm start`. To choose another dashboard port, run `npm start -- --port 4426`.

## Try a supplier request

From the repository root, seed the three synthetic drafts. Rerunning the command keeps any edits you made.

```powershell
uv run --project backend python scripts/seed_demo.py
```

Open the API server's interactive [/docs](http://127.0.0.1:8000/docs). Run `GET /api/requests` and copy a request ID and its current version. Submit Cedar with `POST /api/requests/{id}/submit` and a body containing `expected_version`. The complete request returns HTTP 202, UNDER_REVIEW and the factors behind its score. Poll GET on the request until AWAITING_APPROVAL. The detail response includes the AI summary, recommendation, model, cited fields and values, and AI status. With empty LLM settings it shows UNAVAILABLE and the reviewer can still decide. Submit Northstar to see the missing registration. PATCH its latest version with a complete replacement evidence list, then resubmit. Query `GET /api/requests/{id}/audit` for the ordered history.

At AWAITING_APPROVAL, send the current `expected_version`, `reviewer_label`, `reason` and `action` to `POST /api/requests/{id}/decision`. Actions are approve, reject and request_changes. Approval records the decision and queues one Jira operation. Poll the request detail for its delivery result. In the default simulation a successful delivery has a `SIM-…` key and a null `issue_url`. Request changes allows editing and resubmitting the same request for another review.

If delivery is uncertain, `POST /api/requests/{id}/jira/reconcile` with the current `expected_version` and `reviewer_label` searches for the original request marker. To authorize another create after an inconclusive empty search, the reviewer must first check Jira and send `checked_jira_and_no_issue_exists` set to `true`. That confirmation is recorded in the audit history.

The local single-worker server stores LangGraph checkpoints beside the business database. Keep the two files together when moving the demo. On startup, the server recovers pending review work and resumes decisions already committed to SQLite. A submitted review makes external model calls only when LLM_API_KEY, LLM_BASE_URL and LLM_MODEL are configured. Put real credentials in the ignored root .env. Restart the backend after changing it.

New drafts start at version 1. Every saved edit and transition increments the version. A 409 includes the current request so the caller can review concurrent changes. List counts cover all statuses even when the items are filtered. An optional evidence pointer names a synthetic .txt or .pdf file under sample_data/evidence. Evidence declarations are stored without opening files.

The API migrates vendorflow.sqlite in the repository root on startup. Set DATABASE_PATH to an absolute path to use a separate database. The seed script and Alembic CLI use the same setting.

## Verify the implementation

In `backend/`, run each check in order.

```powershell
uv run ruff check .
uv run ruff format --check .
uv run mypy app
uv run pytest -q
uv run pytest --cov=app --cov-report=term-missing
```

In `frontend/`, run the following commands. The build compares the checked-in types with FastAPI's OpenAPI schema and fails on drift. Use `npm run gen:api` after an intentional API contract change. The generator runs locally and uses its own locked TypeScript version.

```powershell
npm run lint
npm test -- --watch=false
npm run build
```

Phase verification is recorded in [the implementation log](docs/implementation-log.md). [The phase plan](CODEX_PROMPTS.md) defines the remaining interface and evaluation milestones.
