# Implementation log

## 2026-11-18 · Phase 0 · Bootstrap

Verified implementation commit `445c918e76f4ca2c6eaa97f3d9deaf8250275549` (`phase-0: bootstrap`). All gate and dependency measurements below refer to this implementation. Lint, types, tests, coverage, schema generation and the production build were also rerun directly at that commit. Original specifications at `a477018d7322c27a541924c7a0a35c8e7cd30208`.

FastAPI exposes health and public integration settings. The dashboard reads those settings over the loopback proxy and handles loading, errors and retry. The production build validates generated OpenAPI types. The milestone includes Windows CI, four ADRs, the setup guide and a real browser capture. Later-phase directories exist locally and Git will track their contents as the phases are implemented.

### Resolved versions

Sources: `node -v`, `npm -v`, `uv --version`, `uv sync`, and the two npm lockfiles. Complete package versions are in backend/uv.lock, frontend/package-lock.json, and frontend/scripts/package-lock.json.

| Area | Versions |
|---|---|
| Runtime | Node 24.19.0, npm 11.17.0, uv 0.12.5, Python 3.12.14 |
| API | FastAPI 0.164.0, Pydantic 2.14.3, pydantic-settings 2.16.3, uvicorn 0.54.0 |
| Persistence and orchestration dependencies | SQLAlchemy 2.1.9, Alembic 1.20.1, LangGraph 1.2.22, langgraph-checkpoint-sqlite 3.1.3 |
| Backend tools | httpx 0.28.1, openai 3.55.0, structlog 26.1.0, ruff 0.17.5, mypy 2.4.1, pytest 9.2.0, pytest-cov 7.1.0, pytest-socket 0.8.1, respx 0.23.1, Hypothesis 6.170.15 |
| UI and tests | Angular core 22.2.6, build 22.2.7, Material/CDK 22.3.0, TypeScript 6.0.3, ESLint 10.15.0, angular-eslint 22.8.0, Vitest 5.1.1, Playwright 1.65.1, axe integration 4.14.0 |
| Schema tooling | openapi-typescript 7.13.0, TypeScript 5.9.3 |

### Gate results

| Directory | Command | Exit | Observation |
|---|---|---:|---|
| backend | `uv sync` | 0 | Python environment and lockfile created |
| backend | `uv run ruff check .` | 0 | Passed |
| backend | `uv run ruff format --check .` | 0 | 9 files already formatted |
| backend | `uv run mypy app` | 0 | 7 source files checked |
| backend | `uv run pytest -q` | 0 | 3 tests passed with sockets blocked |
| backend | `uv run pytest --cov=app --cov-report=term-missing` | 0 | 3 passed, 49 of 49 bootstrap app statements covered |
| frontend | `npm ci` | 0 | Both locked package trees installed |
| frontend | `npm run gen:api` | 0 | Generated types from the local app |
| frontend | `npm run lint` | 0 | ESLint passed |
| frontend | `npm test -- --watch=false` | 0 | 2 Vitest tests passed |
| frontend | `npm run build` | 0 | Schema check passed, production bundle 287.44 kB raw |
| root | `curl.exe --noproxy "*" --fail --silent --show-error http://127.0.0.1:8426/api/health` | 0 | ok, authentication none, LLM unavailable, Jira simulation |
| frontend | Edge smoke command below | 0 | Settings HTTP 200, dashboard and modes visible, no page error or horizontal overflow at mobile width |

Local servers used `uv run uvicorn app.main:app --host 127.0.0.1 --port 8426` and `$env:VENDORFLOW_API_PORT='8426'` followed by `npm start -- --port 4426`. The default API port was occupied by another application. [Dashboard capture](screenshots/bootstrap-dashboard.png)

<details>
<summary>Edge smoke command, run from frontend</summary>

```powershell
@'
import { chromium, expect } from '@playwright/test';
const browser = await chromium.launch({channel: 'msedge', headless: true});
try {
  const page = await browser.newPage({ viewport: {width: 1280, height: 800} });
  const errors = [];
  page.on('pageerror', err => errors.push(err.message));
  const settingsResponse = page.waitForResponse(r => r.url().endsWith('/api/settings/integrations'));
  await page.goto('http://localhost:4426/', {timeout: 30000});
  const response = await settingsResponse;
  expect(response.status()).toEqual(200);
  await expect(page.getByRole('heading', {name: 'Dashboard'})).toBeVisible();
  const banner = page.getByRole('region', {name: 'Environment and integrations'});
  await expect(banner).toContainText('Demo mode: no authentication');
  await expect(banner).toContainText('AI Unavailable');
  await expect(banner).toContainText('Jira Simulation');
  await page.screenshot({path: '../docs/screenshots/bootstrap-dashboard.png'});
  await page.setViewportSize({width: 375, height: 812});
  await expect(banner).toBeVisible();
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
  expect(errors).toEqual([]);
  console.log('PASS', await page.title(), await response.json(), 'mobile width check passed');
} finally {
  await browser.close();
}
'@ | node --input-type=module
exit $LASTEXITCODE
```

</details>

### Decisions and open items

- The installed Node selects Angular 22. The first npm install reported ERESOLVE because Angular requires TypeScript 6 and openapi-typescript requires TypeScript 5. The generator uses an isolated package tree under frontend/scripts with its own lockfile.
- The first pytest run raised pytest_socket.SocketBlockedError while Windows asyncio created its internal wakeup sockets. The test session now prepares its runner before pytest-socket blocks sockets during tests. HTTP checks call the real app through in-process ASGI transport.
- `npm audit --json` exited 1 with 21 high-severity development-tree findings linked to picomatch. npm reported no compatible automated fix. `npm audit --omit=dev --json` and `npm audit --prefix scripts --json` exited 0 with zero reported findings. Recheck the development chain when a compatible patch becomes available.
- Local checks ran on Windows. Hosted CI awaits a GitHub run. No live Jira or paid LLM calls were made. Domain coverage, acceptance journeys, AI evaluation and Jira delivery belong to later phases.

## 2026-11-18 · Phase 1 · Domain, persistence and request API

Measurements and commands below refer to implementation commit `89bd0712b5a058c95d8598bbab19180042f81a15`.

Implemented draft creation, partial edits, filtered lists with global counts, detail, submit and audit history. SQLite persists business data, evidence declarations and versioned risk assessments. Alembic applies the pinned schema at startup. Reviewed the generated migration and added update/delete guards on audit rows. The complete submit path ends at UNDER_REVIEW in this milestone.

### Decisions

- Used the transition table in architecture.md, as required by the phase prompt. Draft creation uses the initial transition. A submit records the intermediate SUBMITTED event and its routing outcome in the same transaction.
- Every edit or transition advances the version. PATCH replaces the evidence list only when supplied. Conflicts return the current representation. A transaction also rolls back earlier state changes if its audit insert fails.
- Department labels allow 120 characters and service descriptions 4000. The request body limit applies to length-delimited and streamed JSON. Validation errors exclude input values. Declaration pointers identify synthetic .txt or .pdf filenames.
- Seed IDs are deterministic. Re-seeding leaves edited drafts and history intact. No new dependencies were introduced. The Angular UI is scheduled for Phase 4. Its generated request types now match the API.
- During initial verification a method named list shadowed the built-in type and broke mypy and schema export. Renamed it to list_requests. The final runs below passed without this error.

### Local verification

| Working directory | Command | Exit | Result |
|---|---|---:|---|
| backend | `uv run ruff check . ../scripts/seed_demo.py` | 0 | Passed |
| backend | `uv run ruff format --check . ../scripts/seed_demo.py` | 0 | 29 files already formatted |
| backend | `uv run mypy app` | 0 | 21 source files checked |
| backend | `uv run pytest -q` | 0 | 136 passed, sockets blocked |
| backend | `uv run pytest --cov=app --cov-report=term-missing -q` | 0 | 136 passed, 449 of 452 statements covered, 99% reported |
| backend | `uv run coverage report --include='*/app/domain/*,app/domain/*' --fail-under=95` | 0 | 136 of 136 domain statements covered, 100% |
| backend | `uv run alembic check` | 0 | No new upgrade operations detected against the migrated SQLite file |
| frontend | `npm run gen:api`, `npm run lint` | 0 each | Exported types and checked UI sources |
| frontend | `npm test -- --watch=false` | 0 | 2 passed |
| frontend | `npm run build` | 0 | Schema check and production compilation passed |
| root | `uv run --project backend python scripts/seed_demo.py`, twice | 0 each | 3 created, then 3 reported existing |
| frontend | Edge Swagger smoke, PowerShell command below | 0 | GET /api/requests returned HTTP 200 with all three synthetic drafts |

The VF-01, VF-02 and VF-03 checks cover persistence across a new engine, a corrected resubmission, the evidence matrix and risk factors. The suite also covers the complete transition matrix, a stale edit and simultaneous competing edits, database uniqueness definitions, append-only audit protection, rollback of a failed audit insert and body-size validation.

From backend, serve the app with `uv run uvicorn app.main:app --host 127.0.0.1 --port 8427`.

<details>
<summary>Swagger browser check from frontend</summary>

```powershell
@'
import { chromium, expect } from '@playwright/test';
const browser = await chromium.launch({channel:'msedge'});
try {
 const page = await browser.newPage();
 await page.goto('http://127.0.0.1:8427/docs', {waitUntil:'domcontentloaded'});
 const op = page.locator('.opblock-get').filter({has: page.locator('[data-path="/api/requests"]')});
 await op.locator('.opblock-summary').click({timeout:20000});
 await op.getByRole('button',{name:'Try it out'}).click();
 const response = page.waitForResponse(r => r.url() === 'http://127.0.0.1:8427/api/requests');
 await op.getByRole('button',{name:'Execute',exact:true}).click();
 const r = await response;
 expect(r.status()).toBe(200);
 const {items} = await r.json();
 for (const name of ['Cedar Cloud Services','Northstar Advisory','River Apps']) expect(items.some(i=>i.vendor_name===name)).toBe(true);
 console.log('Swagger GET',r.status(), items.map(i=>[i.vendor_name,i.status,i.risk.score,i.missing_evidence]));
} finally { await browser.close(); }
'@ | node --input-type=module
exit $LASTEXITCODE
```

</details>

The prior Phase 0 development dependency advisory remains recorded above. No hosted CI, live Jira, paid LLM or review graph run was part of this gate.

## 2026-11-18 · Phase 2 · Durable human review

Implementation verified at `ae2269ad6ac9037aabcba8b3876e8087de621ff1`. The background review checkpoints each node, publishes AWAITING_APPROVAL after the durable interrupt, and resumes using a persisted decision and the same request UUID. A human approve creates one pending outbox row. Jira dispatch is deferred to Phase 3. Single-worker operation is documented in the README. [LangGraph interrupt semantics](https://docs.langchain.com/oss/python/langgraph/interrupts)

The two schema-bound LLM nodes receive delimited data and have no write tools. The recommendation must cite the original name and typed value of each referenced scalar. Validated responses can be reused during replay. An interrupted provider call is marked unavailable with unknown latency. A configured model may use JSON mode if JSON Schema is unsupported, with at most one repair for invalid output. The installed SDK uses its bundled HTTPX2 transport. Its adapter contract test supplies an in-memory transport with sockets blocked.

| Working directory | Command | Exit | Observation |
|---|---|---:|---|
| backend | `uv run ruff check . ../scripts/seed_demo.py` | 0 | Passed |
| backend | `uv run ruff format --check . ../scripts/seed_demo.py` | 0 | 42 files already formatted |
| backend | `uv run mypy app` | 0 | 31 source files checked |
| backend | `uv run pytest -q --tb=short` | 0 | 148 passed |
| backend | `uv run pytest -q --cov=app --cov-report=term-missing` | 0 | 148 passed, 97% overall |
| backend | `uv run coverage report --include='*/app/domain/*,app/domain/*' --fail-under=95` | 0 | 100% domain coverage |
| backend | `uv run alembic upgrade head`, `uv run alembic check` | 0 each | Local DB migrated, no schema drift |
| frontend | `npm run gen:api`, `npm run lint`, `npm test -- --watch=false`, `npm run build` | 0 each | 2 frontend tests passed, schema and production build passed |
| backend | `uv run python -c "from app.core.config import Settings; print(Settings().llm_configured)"` | 0 | Configuration unavailable. Live LLM submit SKIPPED. LLM_API_KEY, LLM_BASE_URL and LLM_MODEL all unset. Live tokens, latency, and quality NOT MEASURED. |
| root | Local smoke command below | 0 | HTTP 202, risk score 6, AI UNAVAILABLE and AWAITING_APPROVAL |

VF-04 checks malformed JSON, repair, schema fallback, unknown fields, mismatched values, provider failure and injection-shaped vendor text. VF-05 checks the durable pause, rejection and changes without an outbox creation. VF-06 disposes and reinstantiates the app using the same databases, including recovery between decision commit and graph resume. The offline race sends 50 concurrent approvals and observes one success, 49 conflicts, one stored decision, one pending operation and zero issue creations.

Initial integration checks exposed an index declared ahead of its column and the SDK timeout type. Both were corrected before the gate. The earlier development-dependency advisory remains open. Hosted CI was not run. Live Jira was outside this phase. The local Swagger server was restarted on the existing port before the final smoke check.

<details>
<summary>PowerShell smoke from the repository root with the API running</summary>

```powershell
$ErrorActionPreference='Stop'
$api='http://127.0.0.1:8427/api'
$m=Invoke-RestMethod "$api/settings/integrations"
if ($m.llm_mode -ne 'unavailable' -or $m.jira_mode -ne 'simulation') { throw 'Unexpected integration modes' }
$b=(Get-Content -Raw sample_data/requests.json | ConvertFrom-Json)[0]
$b.vendor_name='Cedar Cloud Services - Review Demo'
$d=Invoke-RestMethod "$api/requests" -Method Post -ContentType application/json -Body ($b | ConvertTo-Json -Depth 8)
$u="$api/requests/$($d.id)"
$r=Invoke-WebRequest "$u/submit" -Method Post -ContentType application/json -Body (@{expected_version=$d.version} | ConvertTo-Json)
for ($i=0; $i -lt 30; $i++) { $v=Invoke-RestMethod $u; if ($v.status -ne 'UNDER_REVIEW') { break }; Start-Sleep -Milliseconds 200 }
if ($r.StatusCode -ne 202 -or $v.status -ne 'AWAITING_APPROVAL' -or $v.assessment.ai_status -ne 'UNAVAILABLE') { throw 'Unexpected state' }
[pscustomobject]@{id=$d.id;submit=$r.StatusCode;state=$v.status;ai=$v.assessment.ai_status;score=$v.risk.score} | ConvertTo-Json -Compress
```

</details>
