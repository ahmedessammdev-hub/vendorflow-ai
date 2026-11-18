"""Opt-in local review smoke. One synthetic submit through the FastAPI application."""

import argparse
import asyncio
import json
import os
import sys
from pathlib import Path

import httpx
import httpx2
from sqlalchemy import select

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))
from app.agents.llm_adapter import CompatibleProvider  # noqa: E402
from app.core.config import Settings  # noqa: E402
from app.main import create_app  # noqa: E402
from app.persistence.database import make_engine, migrate  # noqa: E402
from app.persistence.tables import llm_call, vendor_request  # noqa: E402


async def live_review() -> int:
    config = Settings()
    if os.environ.get("VENDORFLOW_LIVE_LLM") != "1" or not config.llm_configured:
        print("VF-04 SKIPPED: enable VENDORFLOW_LIVE_LLM and configure the provider.")
        return 0
    if config.jira_mode != "simulation":
        raise SystemExit("This smoke requires Jira simulation.")
    engine = make_engine(config.database_path)
    try:
        migrate(engine)
        with engine.connect() as conn:
            if conn.scalar(
                select(vendor_request.c.id).filter_by(status="UNDER_REVIEW").limit(1)
            ):
                raise SystemExit(
                    "Finish existing review work before a single-submit smoke."
                )
    finally:
        engine.dispose()

    provider = CompatibleProvider(config)
    codes: list[int] = []

    def observe(response: httpx2.Response) -> None:
        codes.append(response.status_code)

    provider.client._client.event_hooks["response"].append(observe)
    try:
        app = create_app(config, provider=provider)
        async with app.router.lifespan_context(app):
            async with httpx.AsyncClient(
                transport=httpx.ASGITransport(app=app), base_url="http://localhost"
            ) as client:
                seed = json.loads(
                    (ROOT / "sample_data/requests.json").read_text(encoding="utf-8")
                )[0]
                seed["vendor_name"] = "Cedar Cloud Services - NVIDIA review"
                draft = await client.post("/api/requests", json=seed)
                draft.raise_for_status()
                key = draft.json()["id"]
                path = f"/api/requests/{key}"
                submit = await client.post(
                    path + "/submit", json={"expected_version": draft.json()["version"]}
                )
                submit.raise_for_status()
                current = (await client.get(path)).json()
                result = current.get("assessment") or {}
                with app.state.engine.connect() as conn:
                    rows = (
                        conn.execute(
                            select(
                                llm_call.c.node,
                                llm_call.c.model,
                                llm_call.c.outcome,
                                llm_call.c.latency_ms,
                                llm_call.c.tokens_in,
                                llm_call.c.tokens_out,
                            )
                            .filter_by(request_id=key)
                            .order_by(llm_call.c.id)
                        )
                        .mappings()
                        .all()
                    )
                passed = (
                    current["status"] == "AWAITING_APPROVAL"
                    and result.get("ai_status") == "OK"
                )
                print(
                    json.dumps(
                        {
                            "VF-04": "PASS" if passed else "FAIL",
                            "id": key,
                            "request_status": current["status"],
                            "ai_status": result.get("ai_status"),
                            "http_statuses": codes,
                            "calls": [dict(row) for row in rows],
                        }
                    )
                )
                return 0 if passed else 1
    finally:
        provider.client.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--llm-once",
        action="store_true",
        help="Submit one synthetic request using the configured LLM.",
    )
    options = parser.parse_args()
    if options.llm_once:
        raise SystemExit(asyncio.run(live_review()))
    print("Live workflow checks skipped. Use --llm-once for the opt-in LLM check.")
