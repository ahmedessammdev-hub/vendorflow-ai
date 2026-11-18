"""Opt-in local review smoke. One synthetic submit through the FastAPI application."""

import argparse
import asyncio
import json
import os
import socket
import subprocess
import sys
import time
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from tempfile import TemporaryDirectory
from uuid import UUID

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
                seed["vendor_name"] = "Cedar Cloud Services - Provider review"
                draft = await client.post("/api/requests", json=seed)
                draft.raise_for_status()
                key = draft.json()["id"]
                path = f"/api/requests/{key}"
                started = time.monotonic()
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
                            "submit_to_pause_ms": round(
                                (time.monotonic() - started) * 1000
                            ),
                            "ai_status": result.get("ai_status"),
                            "http_statuses": codes,
                            "calls": [dict(row) for row in rows],
                        }
                    )
                )
                return 0 if passed else 1
    finally:
        provider.client.close()


def serve_smoke(port: int) -> None:
    import threading

    import uvicorn

    server = uvicorn.Server(
        uvicorn.Config("app.main:app", host="127.0.0.1", port=port, access_log=False)
    )

    def listen_for_stop() -> None:
        command = sys.stdin.buffer.readline()
        if command == b"crash\n":
            os._exit(0)  # Simulate worker loss against the isolated smoke database.
        server.should_exit = True

    threading.Thread(target=listen_for_stop, daemon=True).start()
    server.run()


@contextmanager
def local_server(database: Path, *, crash: bool = False) -> Iterator[httpx.Client]:
    with socket.socket() as probe:
        probe.bind(("127.0.0.1", 0))
        port = probe.getsockname()[1]
    env = os.environ | {
        "DATABASE_PATH": str(database),
        "JIRA_MODE": "simulation",
        "LLM_API_KEY": "",
        "LLM_MODEL": "",
        "LLM_BASE_URL": "",
    }
    proc = subprocess.Popen(
        [
            sys.executable,
            str(Path(__file__).resolve()),
            "--smoke-server",
            str(port),
        ],
        cwd=ROOT / "backend",
        env=env,
        stdin=subprocess.PIPE,
        stdout=subprocess.DEVNULL,
    )
    try:
        with httpx.Client(
            base_url=f"http://127.0.0.1:{port}/api/", timeout=6, trust_env=False
        ) as client:
            deadline = time.monotonic() + 25
            while time.monotonic() < deadline:
                if proc.poll() is not None:
                    raise RuntimeError("Local verification server stopped.")
                try:
                    if client.get("health").is_success:
                        break
                except httpx.ConnectError:
                    pass
                time.sleep(0.2)
            else:
                raise TimeoutError("Local verification server did not start.")
            yield client
    finally:
        proc.communicate(input=b"crash\n" if crash else b"stop\n", timeout=15)


def poll(
    client: httpx.Client, path: str, statuses: set[str], timeout: int = 30
) -> dict:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        response = client.get(path)
        response.raise_for_status()
        current = response.json()
        if current["status"] in statuses:
            return current
        time.sleep(0.15)
    raise TimeoutError("The request did not reach its expected state.")


def simulated_smoke() -> int:
    checks = {i: ("SKIPPED", "not reached") for i in range(1, 12)}
    checks[4] = ("SKIPPED", "real provider requires a separately authorized evaluation")
    checks[8] = ("SKIPPED", "no authorized live Jira request")

    def verify(i: int, condition: bool, evidence: str) -> None:
        checks[i] = ("PASS" if condition else "FAIL", evidence)
        if not condition:
            raise ValueError(f"VF-{i:02} failed")

    try:
        with TemporaryDirectory(prefix="vendorflow-smoke-") as directory:
            db = Path(directory) / "smoke.sqlite"
            fixture = json.loads(
                (ROOT / "sample_data/requests.json").read_text(encoding="utf-8")
            )[0]
            with local_server(db, crash=True) as api:
                verify(
                    11,
                    api.get("health").json()["jira_mode"] == "simulation"
                    and api.get("metrics").is_success,
                    "running local API, simulation and metrics",
                )
                draft = api.post("requests", json=fixture)
                draft.raise_for_status()
                path = "requests/" + draft.json()["id"]
                verify(
                    1,
                    api.get(path).json()["status"] == "DRAFT",
                    "synthetic draft persisted",
                )
                incomplete = api.post(
                    "requests", json=fixture | {"evidence": []}
                ).json()
                returned = api.post(
                    "requests/" + incomplete["id"] + "/submit",
                    json={"expected_version": incomplete["version"]},
                ).json()
                verify(
                    2,
                    returned["status"] == "NEEDS_CHANGES"
                    and bool(returned["missing_evidence"]),
                    "missing evidence blocks review",
                )
                submitted = api.post(
                    path + "/submit", json={"expected_version": draft.json()["version"]}
                )
                verify(
                    3,
                    submitted.status_code == 202
                    and submitted.json()["risk"]["score"] == 6,
                    "high criticality, cloud and sensitive access score six",
                )
                paused = poll(api, path, {"AWAITING_APPROVAL"})
                verify(
                    5,
                    not paused.get("jira")
                    and paused["assessment"]["ai_status"] == "UNAVAILABLE",
                    "durable human gate with unavailable AI",
                )
            with local_server(db) as api:
                current = api.get(path).json()
                verify(
                    6,
                    current["status"] == "AWAITING_APPROVAL"
                    and current["version"] == paused["version"],
                    "pause persisted across process restart",
                )
                body = {
                    "expected_version": current["version"],
                    "reviewer_label": "Isolated smoke fixture",
                    "action": "approve",
                    "reason": "Synthetic browser-independent verification",
                }
                api.post(path + "/decision", json=body).raise_for_status()
                end = poll(api, path, {"JIRA_CREATED"})
                verify(
                    7,
                    end["jira"]["mode"] == "simulation"
                    and end["jira"]["issue_key"].startswith("SIM-")
                    and end["jira"]["issue_url"] is None,
                    "labeled simulated issue without link",
                )
                replay = api.post(path + "/decision", json=body)
                verify(
                    9,
                    replay.status_code == 409
                    and api.get(path).json()["jira"]["attempts"] == 1,
                    "stale approval conflicts, single attempt",
                )
                audit = api.get(path + "/audit").json()
                verify(
                    10,
                    any(e["detail"].get("reason") == body["reason"] for e in audit)
                    and audit[-1]["to_status"] == "JIRA_CREATED",
                    "recorded human reason and ordered delivery history",
                )
    except Exception as exc:
        print("Smoke error:", type(exc).__name__, file=sys.stderr)
        success = False
    else:
        success = True
    for i, (status, reason) in checks.items():
        print(f"VF-{i:02} {status} — {reason}")
    return 0 if success else 1


def live_jira(key: UUID, version: int, reviewer: str, reason: str, port: int) -> int:
    from app.integration.jira_client import LiveJira

    config = Settings()
    if (
        os.getenv("VENDORFLOW_LIVE_JIRA") != "1"
        or config.jira_mode != "live"
        or not reviewer.strip()
        or not reason.strip()
    ):
        raise SystemExit(
            "Live Jira needs live mode, explicit enablement and a human reviewer decision."
        )
    jira = LiveJira(config)
    try:
        with httpx.Client(
            base_url=f"http://127.0.0.1:{port}/api/", timeout=15, trust_env=False
        ) as api:
            if api.get("health").json()["jira_mode"] != "live":
                raise ValueError("API is not in live mode.")
            path = f"requests/{key}"
            row = api.get(path).json()
            if (
                row["version"] != version
                or row["status"] != "AWAITING_APPROVAL"
                or row.get("jira")
            ):
                raise ValueError("Request is not at the expected human review gate.")
            body = {
                "expected_version": version,
                "reviewer_label": reviewer,
                "reason": reason,
                "action": "approve",
            }
            api.post(path + "/decision", json=body).raise_for_status()
            final = poll(api, path, {"JIRA_CREATED", "JIRA_FAILED"}, 120)
            if final["status"] != "JIRA_CREATED":
                raise RuntimeError(
                    "Verify the original delivery manually. No retry issued."
                )
            issue_key = final["jira"]["issue_key"]
            result = jira.call(
                "GET",
                f"/rest/api/3/issue/{issue_key}",
                params={"fields": "labels,description"},
            )
            fields = result["fields"]
            marker = f"vf-{key}"
            assert (
                marker in fields["labels"]
                and fields["description"]["type"] == "doc"
                and str(key) in json.dumps(fields["description"])
            )
            assert api.post(path + "/decision", json=body).status_code == 409
            for delay in (0, 2, 5, 15, 30):
                time.sleep(delay)
                match = jira.search(key)
                if match and match.key == issue_key:
                    break
            else:
                raise RuntimeError("Marker search did not confirm a unique issue.")
            print("VF-08 PASS", issue_key)
            return 0
    finally:
        jira.http.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--llm-once",
        action="store_true",
        help="Submit one synthetic request using the configured LLM.",
    )
    parser.add_argument("--live-jira", type=UUID, metavar="REQUEST_ID")
    parser.add_argument("--version", type=int)
    parser.add_argument("--reviewer", default="")
    parser.add_argument("--reason", default="")
    parser.add_argument("--port", type=int, default=8000)
    parser.add_argument("--smoke-server", type=int, help=argparse.SUPPRESS)
    options = parser.parse_args()
    if options.smoke_server:
        serve_smoke(options.smoke_server)
        raise SystemExit(0)
    if options.live_jira:
        if options.version is None:
            parser.error("Supply the version you reviewed.")
        raise SystemExit(
            live_jira(
                options.live_jira,
                options.version,
                options.reviewer,
                options.reason,
                options.port,
            )
        )
    if options.llm_once:
        raise SystemExit(asyncio.run(live_review()))
    raise SystemExit(simulated_smoke())
