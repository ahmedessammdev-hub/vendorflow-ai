# Metrics plan — the numbers this project must produce

Goal: replace adjectives with measurements you can quote in an interview. Every number is produced by a script, written to `docs/metrics.md` with the date, commit SHA, machine summary, LLM mode and Jira mode. Nothing in that file is typed by hand. A metric that could not be measured is written as `NOT MEASURED` with the reason.

Targets below are goals to check against, not claims. Report the real value even when it misses.

## A. Correctness and safety

| Metric | How it is measured | Target |
|---|---|---|
| VF acceptance criteria passing | pytest tests tagged per VF-ID | 10 of 10 automated; VF-08 live or SKIPPED |
| Jira creates before approval | counter on the mock across the whole suite | 0 |
| Duplicate issues under 50 concurrent approvals | `scripts/load_test.py --race 50` | 1 operation, 1 create call |
| Fault-injection cases handled | 401, 429, 500, read timeout, reset, crash while in flight | 6 of 6, no duplicate |
| Restart recovery | paused at interrupt, kill, restart, resume | pass |
| Property-test examples | Hypothesis run count with zero invariant violations | ≥ 500 examples |

## B. Code quality

| Metric | How | Target |
|---|---|---|
| Backend tests | `pytest -q` passed / failed / skipped | 0 failed |
| Coverage, overall | pytest-cov | ≥ 85 % |
| Coverage, `domain/` | pytest-cov | ≥ 95 % |
| Lint and type errors | ruff, mypy, ESLint | 0 |
| Frontend unit tests | `npm test` | 0 failed |
| E2E journeys | Playwright | 2 of 2 |
| Accessibility | axe-core scan of 4 pages | 0 serious or critical |
| Initial JS bundle | Angular build output | report the size |

## C. Performance (local machine, stated in the report)

| Metric | How | Target |
|---|---|---|
| API latency p50 / p95, read endpoints | `load_test.py`, 200 requests each | p95 < 100 ms |
| API latency p50 / p95, create and decision | same | p95 < 200 ms |
| Submit → AWAITING_APPROVAL, fake LLM | timed in integration test | < 1 s |
| Submit → AWAITING_APPROVAL, live LLM | `verify_workflow.py` | report it |

## D. LLM quality (only with a real provider; otherwise NOT MEASURED)

Run `scripts/run_llm_eval.py` on `sample_data/eval/golden.jsonl`: 20 synthetic requests, each with an expected recommendation label written by hand and the reason for it.

| Metric | Definition | Target |
|---|---|---|
| Schema-valid rate | outputs passing Pydantic on first try, and after one repair | ≥ 95 % after repair |
| Grounding rate | outputs whose cited fields all exist | 100 % |
| Label agreement | recommendation equals expected label | report it, with the confusion table |
| Injection resistance | 3 adversarial cases still schema-valid and never change status | 3 of 3 |
| Latency p50 / p95 per node | from `LlmCall` | report it |
| Tokens and cost per request | from `LlmCall`, price taken from `.env` | report it |

Label agreement on 20 cases is a sanity check, not a benchmark. Say so in the report.

## E. Live checks (opt-in)

`scripts/verify_workflow.py` runs against the running server and prints one line per VF-ID: `PASS`, `FAIL` or `SKIPPED` with the reason. With `JIRA_MODE=live` it creates exactly one issue in the user's test project, prints the key, then fetches that issue back to confirm the label and description.

## Output format of `docs/metrics.md`

```text
Generated: <UTC timestamp>   Commit: <sha>   OS: <…>   Python: <…>   Node: <…>
LLM mode: live(<model>) | unavailable | fake      Jira mode: simulation | live

| Section | Metric | Value | Target | Status |
```

The README shows a short table copied by the script from this file, so the two cannot drift.
