"""Local ASGI benchmark. All decisions and Jira creates use isolated synthetic fixtures."""

import argparse
import asyncio
import json
import math
import sys
from collections import Counter
from pathlib import Path
from tempfile import TemporaryDirectory
from time import perf_counter
from typing import Any

import httpx
from sqlalchemy import func, select

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))
sys.path.insert(0, str(ROOT / "backend/tests/integration"))
from test_review import DRAFT, FakeProvider  # noqa: E402

from app.core.config import Settings  # noqa: E402
from app.domain.models import RequestView  # noqa: E402
from app.integration.jira_client import Issue  # noqa: E402
from app.integration.jira_sim import SimulatedJira  # noqa: E402
from app.main import create_app  # noqa: E402
from app.persistence.tables import jira_operation, simulated_issue  # noqa: E402


def summarize(values: list[float]) -> dict[str, float]:
    ordered = sorted(values)
    return {
        p: round(ordered[math.ceil(len(values) * q) - 1], 2)
        for p, q in [("p50_ms", 0.5), ("p95_ms", 0.95)]
    }


async def measure(samples: int, race: int) -> dict[str, Any]:
    with TemporaryDirectory(prefix="vendorflow-load-") as directory:
        app = create_app(
            Settings(
                database_path=Path(directory) / "load.sqlite",
                llm_api_key=None,
                jira_mode="simulation",
            ),
            provider=FakeProvider(),
        )
        times: dict[str, list[float]] = {}
        counter: Counter[str] = Counter()

        class CountedSimulation(SimulatedJira):
            def create(self, request: RequestView) -> Issue:
                counter[str(request.id)] += 1
                return super().create(request)

        async with (
            app.router.lifespan_context(app),
            httpx.AsyncClient(
                transport=httpx.ASGITransport(app=app), base_url="http://benchmark"
            ) as http,
        ):
            app.state.dispatcher.clients["simulation"] = CountedSimulation(
                app.state.engine
            )

            async def timed(
                name: str, method: str, path: str, **kwargs: Any
            ) -> dict[str, Any]:
                start = perf_counter()
                r = await http.request(method, path, **kwargs)
                elapsed = (perf_counter() - start) * 1000
                r.raise_for_status()
                times.setdefault(name, []).append(elapsed)
                return r.json()

            for i in range(samples + 1):
                row = await timed(
                    "create",
                    "POST",
                    "/api/requests",
                    json=DRAFT | {"vendor_name": f"Measurement supplier {i}"},
                )
                path = "/api/requests/" + row["id"]
                start = perf_counter()
                submit = await http.post(
                    path + "/submit", json={"expected_version": row["version"]}
                )
                submit.raise_for_status()
                waiting = await http.get(path)
                waiting.raise_for_status()
                current = waiting.json()
                assert (
                    current["status"] == "AWAITING_APPROVAL"
                    and current["assessment"]["ai_status"] == "OK"
                )
                if i < samples:
                    times.setdefault("submit_to_pause", []).append(
                        (perf_counter() - start) * 1000
                    )
                decision = {
                    "expected_version": current["version"],
                    "reviewer_label": "Synthetic benchmark",
                    "action": "approve",
                    "reason": "Isolated workflow measurement",
                }
                if i < samples:
                    await timed("decision", "POST", path + "/decision", json=decision)
                else:
                    times["create"].pop()
            race_results = await asyncio.gather(
                *(http.post(path + "/decision", json=decision) for _ in range(race))
            )
            codes = Counter(r.status_code for r in race_results)
            with app.state.engine.connect() as conn:
                ops = conn.scalar(
                    select(func.count())
                    .select_from(jira_operation)
                    .where(jira_operation.c.request_id == current["id"])
                )
                issues = conn.scalar(
                    select(func.count())
                    .select_from(simulated_issue)
                    .where(simulated_issue.c.marker == "vf-" + current["id"])
                )
            assert (
                codes[200] == 1
                and codes[409] == race - 1
                and ops == issues == counter[current["id"]] == 1
            )
            for name, url in [
                ("list", "/api/requests"),
                ("detail", path),
                ("audit", path + "/audit"),
                ("metrics", "/api/metrics"),
                ("health", "/api/health"),
            ]:
                for _ in range(samples):
                    await timed(name, "GET", url)
            return {
                "samples": samples,
                "scope": "in-process ASGI, wall time includes background work",
                "llm": "test fixture",
                "jira": "simulation",
                "latencies": {k: summarize(v) for k, v in times.items()},
                "race": {
                    "clients": race,
                    "accepted": codes[200],
                    "conflicts": codes[409],
                    "operations": ops,
                    "create_calls": counter[current["id"]],
                    "issues": issues,
                },
            }


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--samples", type=int, default=200)
    parser.add_argument("--race", type=int, default=50)
    args = parser.parse_args()
    if not 1 <= args.samples <= 1000 or not 2 <= args.race <= 100:
        parser.error("Use 1–1000 samples and 2–100 race participants.")
    print(json.dumps(asyncio.run(measure(args.samples, args.race)), indent=2))
