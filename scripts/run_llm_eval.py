"""Evaluate synthetic cases through the production review graph; never approve a case."""

import argparse
import asyncio
import json
import math
import subprocess
import sys
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path
from tempfile import TemporaryDirectory
from time import perf_counter
from typing import Any

import httpx
from pydantic import BaseModel, ValidationError
from sqlalchemy import select

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))
from app.agents.llm_adapter import CompatibleProvider, Reply  # noqa: E402
from app.agents.schemas import Recommendation  # noqa: E402
from app.core.config import Settings  # noqa: E402
from app.domain.models import CreateRequest  # noqa: E402
from app.main import create_app  # noqa: E402
from app.persistence.tables import llm_call  # noqa: E402


class MeasuredProvider:
    def __init__(self, provider: CompatibleProvider) -> None:
        self.provider = provider
        self.model = provider.model
        self.valid: dict[str, list[bool]] = {}

    def complete(
        self, schema: type[BaseModel], system: str, data: str, json_mode: bool
    ) -> Reply:
        reply = self.provider.complete(schema, system, data, json_mode)
        try:
            schema.model_validate_json(reply.content, strict=True)
            valid = True
        except ValidationError:
            valid = False
        self.valid.setdefault(schema.__name__, []).append(valid)
        return reply


def cases() -> list[dict[str, Any]]:
    rows = [
        json.loads(line)
        for line in (ROOT / "sample_data/eval/golden.jsonl")
        .read_text(encoding="utf-8")
        .splitlines()
        if line.strip()
    ]
    if (
        len(rows) != 20
        or len({r["id"] for r in rows}) != len(rows)
        or sum(r["adversarial"] for r in rows) != 3
    ):
        raise ValueError(
            "Expected twenty distinct cases including three adversarial cases."
        )
    for row in rows:
        CreateRequest.model_validate(row["request"])
        if (
            row["expected"]
            not in Recommendation.model_json_schema()["properties"]["recommendation"][
                "enum"
            ]
            or not row["reason"]
        ):
            raise ValueError("Missing evaluation label or explanation.")
    return rows


async def one(
    case: dict[str, Any],
    directory: Path,
    provider: CompatibleProvider,
    settings: Settings,
) -> dict[str, Any]:
    cfg = settings.model_copy(
        update={
            "database_path": directory / (case["id"] + ".sqlite"),
            "jira_mode": "simulation",
        }
    )
    observed = MeasuredProvider(provider)
    app = create_app(cfg, provider=observed)
    async with (
        app.router.lifespan_context(app),
        httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app), base_url="http://local"
        ) as http,
    ):
        draft = await http.post("/api/requests", json=case["request"])
        draft.raise_for_status()
        path = "/api/requests/" + draft.json()["id"]
        started = perf_counter()
        submitted = await http.post(
            path + "/submit", json={"expected_version": draft.json()["version"]}
        )
        submitted.raise_for_status()
        detail = (await http.get(path)).json()
        submit_to_pause_ms = round((perf_counter() - started) * 1000)
        if detail["status"] != "AWAITING_APPROVAL" or detail.get("jira"):
            raise RuntimeError("Evaluation did not end at the human gate.")
        assessment = detail["assessment"]
        advice = assessment.get("recommendation")
        with app.state.engine.connect() as conn:
            records = [
                dict(r)
                for r in conn.execute(
                    select(
                        llm_call.c.node,
                        llm_call.c.model,
                        llm_call.c.attempt,
                        llm_call.c.outcome,
                        llm_call.c.latency_ms,
                        llm_call.c.tokens_in,
                        llm_call.c.tokens_out,
                    )
                ).mappings()
            ]
    expected_stages = ["IntakeSummary", "Recommendation"]
    result = {
        "id": case["id"],
        "expected": case["expected"],
        "adversarial": case["adversarial"],
        "status": assessment["ai_status"],
        "label": advice["recommendation"] if advice else None,
        "submit_to_pause_ms": submit_to_pause_ms,
        "first_schema": all(observed.valid.get(n, [False])[0] for n in expected_stages),
        "final_schema": all(any(observed.valid.get(n, [])) for n in expected_stages),
        "grounded": bool(advice),
        "human_gate": True,
        "calls": records,
    }
    print(case["id"], result["status"], flush=True)
    return result


def quantile(values: list[int | float], fraction: float) -> float | None:
    return sorted(values)[math.ceil(len(values) * fraction) - 1] if values else None


async def evaluate(output: Path, all_cases: bool) -> None:
    items = cases()
    revision = subprocess.check_output(
        ["git", "rev-parse", "HEAD"], cwd=ROOT, text=True
    ).strip()
    cfg = Settings()
    if not cfg.llm_configured:
        raise SystemExit("No configured model. No live evaluation was sent.")
    provider = CompatibleProvider(cfg)
    try:
        with TemporaryDirectory(prefix="vendorflow-eval-") as temp:
            folder = Path(temp)
            results = [await one(items[0], folder, provider, cfg)]
            if all_cases or any(c["outcome"] == "OK" for c in results[0]["calls"]):
                limit = asyncio.Semaphore(3)

                async def bounded(case: dict[str, Any]) -> dict[str, Any]:
                    async with limit:
                        return await one(case, folder, provider, cfg)

                results.extend(await asyncio.gather(*(bounded(c) for c in items[1:])))
    finally:
        provider.client.close()
    calls = [call for row in results for call in row["calls"]]
    labels = [r for r in results if r["label"]]
    known_tokens = bool(calls) and all(
        c["tokens_in"] is not None and c["tokens_out"] is not None for c in calls
    )
    tokens_in = sum(c["tokens_in"] for c in calls) if known_tokens else None
    tokens_out = sum(c["tokens_out"] for c in calls) if known_tokens else None
    cost = None
    if (
        tokens_in is not None
        and cfg.llm_input_usd_per_million is not None
        and cfg.llm_output_usd_per_million is not None
    ):
        cost = (
            tokens_in * cfg.llm_input_usd_per_million
            + tokens_out * cfg.llm_output_usd_per_million
        ) / 1e6
    latencies = {}
    for node in sorted({c["node"] for c in calls}):
        vals = [
            c["latency_ms"]
            for c in calls
            if c["node"] == node and c["latency_ms"] is not None
        ]
        latencies[node] = {
            "p50_ms": quantile(vals, 0.5),
            "p95_ms": quantile(vals, 0.95),
        }
    report = {
        "utc": datetime.now(UTC).isoformat(),
        "sha": revision,
        "model": cfg.llm_model,
        "timeout_seconds": cfg.llm_timeout_seconds,
        "reasoning_effort": cfg.llm_reasoning_effort,
        "max_tokens": cfg.llm_max_tokens,
        "planned": len(items),
        "attempted": len(results),
        "stop_reason": "Initial review unavailable; remaining cases not sent."
        if len(results) < len(items)
        else None,
        "first_schema": sum(r["first_schema"] for r in results),
        "final_schema": sum(r["final_schema"] for r in results),
        "grounded": len(labels),
        "agreement": sum(r["label"] == r["expected"] for r in results),
        "adversarial_pass": sum(
            r["adversarial"] and r["final_schema"] and r["grounded"] and r["human_gate"]
            for r in results
        ),
        "confusion": dict(
            Counter(
                r["expected"] + " -> " + (r["label"] or "NO OUTPUT") for r in results
            )
        ),
        "latencies": latencies,
        "tokens_in": tokens_in,
        "tokens_out": tokens_out,
        "total_cost_usd": cost,
        "cases": results,
    }
    output.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(f"Saved {len(results)}/{len(items)} cases to {output}", flush=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--live",
        action="store_true",
        help="Send the synthetic set to the configured provider.",
    )
    parser.add_argument("--output", type=Path, default=ROOT / "docs/evaluation.json")
    parser.add_argument(
        "--all-cases",
        action="store_true",
        help="Attempt the complete authorized set even if the first case is unavailable.",
    )
    args = parser.parse_args()
    if args.live:
        asyncio.run(evaluate(args.output, args.all_cases))
    else:
        print(f"Validated {len(cases())} labeled cases. Live inference skipped.")
