import asyncio
import json
from collections.abc import AsyncIterator, Callable, Coroutine, Iterator
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any
from uuid import uuid4

import httpx
import pytest
from fastapi import FastAPI
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError

from app.core.config import Settings
from app.main import create_app
from app.persistence.database import write_transaction
from app.persistence.tables import assessment, audit_event, jira_operation

Run = Callable[[Coroutine[Any, Any, None]], None]
BASE = "/api/requests"
CEDAR = {
    "vendor_name": "Cedar Cloud Services",
    "business_criticality": "high",
    "service_category": "cloud_hosting",
    "sensitive_data_access": True,
    "requester_department": "Technology",
    "service_description": "Host synthetic projects.",
}
PROOFS = [
    {"kind": k, "present": True}
    for k in ("business_registration", "security_questionnaire", "service_sla")
]


@pytest.fixture
def app(tmp_path: Path) -> Iterator[FastAPI]:
    application = create_app(
        Settings(database_path=tmp_path / "test.sqlite", llm_api_key=None)
    )
    yield application
    application.state.engine.dispose()


@asynccontextmanager
async def client(app: FastAPI) -> AsyncIterator[httpx.AsyncClient]:
    async with app.router.lifespan_context(app):
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app), base_url="http://test"
        ) as http:
            yield http


def test_vf01_draft_persists_across_new_engine_and_html_is_text(
    app: FastAPI, run_async: Run
) -> None:
    async def journey() -> None:
        markup = "<script type='application/json'>{}</script>"
        async with client(app) as http:
            result = await http.post(BASE, json=CEDAR | {"vendor_name": markup})
            assert result.status_code == 201
            draft = result.json()
            assert draft["status"] == "DRAFT" and draft["version"] == 1
            assert draft["vendor_name"] == markup
        other = create_app(app.state.settings)
        async with client(other) as http:
            key = BASE + "/" + draft["id"]
            response = await http.get(key)
            assert response.headers["content-type"].startswith("application/json")
            assert response.json() == draft
            assert (await http.get(key + "/audit")).json()[0]["event_type"] == "created"

    run_async(journey())


def test_vf02_return_correct_resubmit_and_vf03_risk(
    app: FastAPI, run_async: Run
) -> None:
    async def journey() -> None:
        async with client(app) as http:
            body = CEDAR | {
                "evidence": [*PROOFS[:2], {"kind": "service_sla", "present": False}]
            }
            draft = (await http.post(BASE, json=body)).json()
            path = BASE + "/" + draft["id"]
            submit = await http.post(path + "/submit", json={"expected_version": 1})
            assert submit.status_code == 200
            returned = submit.json()
            assert returned["status"] == "NEEDS_CHANGES" and returned[
                "missing_evidence"
            ] == ["service_sla"]
            with app.state.engine.connect() as conn:
                assert conn.scalar(select(func.count()).select_from(assessment)) == 0
                assert (
                    conn.scalar(select(func.count()).select_from(jira_operation)) == 0
                )
            stale = await http.patch(
                path, json={"expected_version": 1, "evidence": PROOFS}
            )
            assert stale.status_code == 409 and stale.json()["current"] == returned
            edit = (
                await http.patch(
                    path,
                    json={"expected_version": returned["version"], "evidence": PROOFS},
                )
            ).json()
            assert (
                edit["missing_evidence"] == []
                and edit["vendor_name"] == CEDAR["vendor_name"]
            )
            resubmitted = await http.post(
                path + "/submit", json={"expected_version": edit["version"]}
            )
            assert resubmitted.status_code == 202
            current = resubmitted.json()
            assert current["status"] == "UNDER_REVIEW"
            assert current["risk"]["score"] == 6 and current["risk"]["band"] == "HIGH"
            assert [factor["points"] for factor in current["risk"]["factors"]] == [
                3,
                2,
                1,
            ]
            with app.state.engine.connect() as conn:
                saved = conn.execute(select(assessment)).mappings().one()
                assert (saved["request_version"], saved["score"], saved["factors"]) == (
                    current["version"],
                    6,
                    current["risk"]["factors"],
                )
            waiting = (await http.get(path)).json()
            assert (
                waiting["status"] == "AWAITING_APPROVAL"
                and waiting["version"] == current["version"] + 1
            )
            assert waiting.pop("assessment")["ai_status"] == "UNAVAILABLE"
            for method, endpoint, payload in [
                ("PATCH", path, {"vendor_name": "Change"}),
                ("POST", path + "/submit", {}),
            ]:
                result = await http.request(
                    method,
                    endpoint,
                    json={"expected_version": current["version"], **payload},
                )
                assert result.status_code == 409 and result.json()["current"] == waiting
            log = (await http.get(path + "/audit")).json()
            assert [e["to_status"] for e in log] == [
                "DRAFT",
                "SUBMITTED",
                "NEEDS_CHANGES",
                "NEEDS_CHANGES",
                "SUBMITTED",
                "UNDER_REVIEW",
                "AWAITING_APPROVAL",
            ]
            assert [e["detail"]["version"] for e in log] == list(range(1, 8))
            filtered = (await http.get(BASE, params={"status": "DRAFT"})).json()
            assert (
                filtered["items"] == [] and filtered["counts"]["AWAITING_APPROVAL"] == 1
            )
            assert (await http.get(BASE)).json()["items"] == [waiting]
            assert (await http.get(f"{BASE}/{uuid4()}/audit")).status_code == 404

    run_async(journey())


def test_vf01_field_validation_and_body_limits(app: FastAPI, run_async: Run) -> None:
    async def run() -> None:
        async with client(app) as http:
            for name, value in [
                ("vendor_name", "a"),
                ("vendor_name", "x" * 121),
                ("service_description", "x" * 4001),
                ("requester_department", " "),
                ("service_category", "invalid"),
                ("sensitive_data_access", "yes"),
                ("status", "APPROVED"),
                ("evidence", [PROOFS[0], PROOFS[0]]),
                ("evidence", [{"kind": "unknown", "present": True}]),
            ]:
                response = await http.post(BASE, json=CEDAR | {name: value})
                assert response.status_code == 422 and response.json()["detail"]
                assert all("input" not in error for error in response.json()["detail"])
            missing = await http.post(BASE, json={})
            assert {err["loc"][-1] for err in missing.json()["detail"]} == set(CEDAR)
            draft = (await http.post(BASE, json=CEDAR)).json()
            for patch in [
                {"expected_version": 1},
                {"expected_version": 1, "vendor_name": None},
                {"expected_version": 1, "evidence": [PROOFS[0], PROOFS[0]]},
                {"vendor_name": "Acme"},
            ]:
                assert (
                    await http.patch(f"{BASE}/{draft['id']}", json=patch)
                ).status_code == 422
            raw = json.dumps({"service_description": "x" * 65536}).encode()

            async def chunks() -> AsyncIterator[bytes]:
                yield raw[:100]
                yield raw[100:]

            for content in (raw, chunks()):
                response = await http.post(
                    BASE, content=content, headers={"content-type": "application/json"}
                )
                assert response.status_code == 413

    run_async(run())


def test_atomic_edits_and_append_only_audit(app: FastAPI, run_async: Run) -> None:
    async def race() -> None:
        async with client(app) as http:
            draft = (await http.post(BASE, json=CEDAR)).json()
            path = BASE + "/" + draft["id"]
            responses = await asyncio.gather(
                *(
                    http.patch(path, json={"expected_version": 1, "vendor_name": name})
                    for name in ("First Supplier", "Second Supplier")
                )
            )
            assert sorted(r.status_code for r in responses) == [200, 409]
            winner = next(r.json() for r in responses if r.status_code == 200)
            assert (await http.get(path)).json() == winner and winner["version"] == 2
            assert len((await http.get(path + "/audit")).json()) == 2
            for stmt in (
                audit_event.update().values(event_type="other"),
                audit_event.delete(),
            ):
                with (
                    pytest.raises(IntegrityError, match="append-only"),
                    write_transaction(app.state.engine) as conn,
                ):
                    conn.execute(stmt)
            with app.state.engine.connect() as conn:
                assert conn.exec_driver_sql("PRAGMA journal_mode").scalar() == "wal"
                assert conn.exec_driver_sql("PRAGMA foreign_keys").scalar() == 1
                assert conn.exec_driver_sql("PRAGMA busy_timeout").scalar() == 5000

    run_async(race())
