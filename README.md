# VendorFlow AI

A local portfolio demo for procurement review using synthetic supplier data. The bootstrap release serves an empty dashboard and reports the configured integration modes. The full journey and acceptance criteria are in [the product spec](docs/spec.md) and [approved addendum](docs/spec-addendum.md).

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

## Verify the bootstrap

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

Phase verification is recorded in [the implementation log](docs/implementation-log.md). [The phase plan](CODEX_PROMPTS.md) defines later request, review, integration and evaluation milestones.
