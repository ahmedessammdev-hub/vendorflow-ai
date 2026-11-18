# VendorFlow verification and measurements

Generated 2026-11-18T19:29:13+00:00 at commit `a05d0151a6785ecadf31d3a84a046bd8160ac188`. Windows-11-10.0.26300-SP0, AMD64, Python 3.12.14, Node v24.19.0.

Local gates use Jira simulation. Randomized tests and load measurements use offline or fixture AI. Load measurements use 200 observations per endpoint through in-process ASGI and include background work. The separate live evaluation used auto at `2c58be43293bafa17a3f8db5817e623eda63fb35`, 20/20 cases attempted.

| Metric | Measured value | Target | Status |
|---|---|---|---|
| Automated VF criteria | 10/10 | 10/10 | PASS |
| Backend tests | 177/177 | all pass | PASS |
| Pre-approval Jira creates | 0 | 0 | PASS |
| Property-test sequences | 560 | >=500 | PASS |
| Fault paths exercised | 6/6 | 6/6 | PASS |
| Coverage, overall | 94.7% | ≥85% | PASS |
| Coverage, domain | 100.0% | ≥95% | PASS |
| Lint and type errors | 0 | 0 | PASS |
| Frontend tests | 5 passed | 0 failures | PASS |
| Initial JavaScript | 373,172 bytes | report | Reported |
| Browser journeys | 2/2 | 2/2 | PASS |
| Serious/critical axe findings | 0 on 5 screens | 0 on ≥4 | PASS |
| Paused review survives real server restart | PASS | pass | PASS |
| 50 concurrent approvals | 1 accepted, 49 conflicts, 1 operation, 1 create, 1 issue | 1 operation and 1 create | PASS |
| API create | p50 2.84 / p95 3.78 ms | p95 < 200 ms | PASS |
| API submit_to_pause | p50 27.1 / p95 35.22 ms | p95 < 1000 ms | PASS |
| API decision | p50 14.95 / p95 18.2 ms | p95 < 200 ms | PASS |
| API list | p50 10.96 / p95 16.23 ms | p95 < 100 ms | PASS |
| API detail | p50 2.07 / p95 2.8 ms | p95 < 100 ms | PASS |
| API audit | p50 1.65 / p95 2.08 ms | p95 < 100 ms | PASS |
| API metrics | p50 1.46 / p95 1.86 ms | p95 < 100 ms | PASS |
| API health | p50 0.58 / p95 0.74 ms | p95 < 100 ms | PASS |
| First-pass schema validity | 12/20 (60.0%) | report | Reported |
| Schema validity after repair | 12/20 (60.0%) | ≥95% | MISS |
| Grounded recommendation per case | 13/20 (65.0%) | ≥100% | MISS |
| Label agreement | 8/20 (40.0%) | report | Reported |
| Injection cases | 2/3 | 3/3 | MISS |
| Complete validated live assessments | 7/20 | report | Reported |
| Live cases stopped for human approval | 20/20 | all cases | PASS |
| Validated intake_summary per attempted case | 13/20 | report | Reported |
| Validated recommendation per attempted case | 13/20 | report | Reported |
| Token usage coverage | 34/47 attempts reported usage | report | Reported |
| Recorded token subtotal | 20138 input / 36464 output | report | Reported |
| Live intake_summary attempt latency | p50 15433 / p95 60035 ms | report | Reported |
| Live recommendation attempt latency | p50 19698 / p95 60026 ms | report | Reported |
| Live submit to human pause | 68985.4 ms mean (20 cases) | report | Reported |
| Live tokens per attempted case | NOT MEASURED — usage unavailable | report | Reported |
| Live cost per attempted case | NOT MEASURED — verified prices or usage unavailable | report | Reported |
| VF-08 real Jira | SKIPPED — no authorized live Jira site or issue | opt-in | Reported |

## Live label confusion counts

- approve_review -> NO OUTPUT: 4
- approve_review -> approve_review: 2
- approve_review -> request_more_info: 1
- escalate -> NO OUTPUT: 1
- escalate -> escalate: 3
- escalate -> request_more_info: 2
- request_more_info -> NO OUTPUT: 2
- request_more_info -> approve_review: 2
- request_more_info -> request_more_info: 3

Agreement on these hand-labeled synthetic cases is a sanity check. Unknown usage and prices remain unmeasured.

Live evaluation: [sanitized per-case records](evaluation.json), code revision `2c58be43293bafa17a3f8db5817e623eda63fb35`.

Earlier NVIDIA evaluation at `b5857ce3bd2efa225e443c9424d652054ae3626a`: 1/20 cases attempted, 0 grounded recommendations. Initial review unavailable; remaining cases not sent. [Separate NVIDIA record](evaluation-nvidia.json).

## Commands

| Directory | Command | Exit |
|---|---|---|
| . | `git rev-parse HEAD` | 0 |
| . | `node -v` | 0 |
| backend | `uv run ruff check . ../scripts` | 0 |
| backend | `uv run ruff format --check . ../scripts` | 0 |
| backend | `uv run mypy app` | 0 |
| backend | `uv run alembic upgrade head` | 0 |
| backend | `uv run alembic check` | 0 |
| backend | `uv run pytest -q -s --cov=app --cov-report=term-missing --junitxml=../.runtime/metrics/backend.xml` | 0 |
| backend | `uv run coverage json -o ../.runtime/metrics/coverage.json` | 0 |
| frontend | `npm run gen:api` | 0 |
| frontend | `npm run lint` | 0 |
| frontend | `npm test -- --watch=false` | 0 |
| frontend | `npm run build` | 0 |
| frontend | `npx playwright test` | 0 |
| . | `uv run --project backend python scripts/verify_workflow.py` | 0 |
| . | `uv run --project backend python scripts/load_test.py --race 50` | 0 |
