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
