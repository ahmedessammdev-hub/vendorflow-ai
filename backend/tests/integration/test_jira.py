import json
from collections.abc import Callable, Coroutine
from pathlib import Path
from typing import Any
from uuid import UUID

import httpx
import pytest
import respx
from pydantic import SecretStr, ValidationError
from sqlalchemy import func, select

from app.agents.schemas import HumanDecision
from app.core.config import Settings
from app.domain.models import RequestView
from app.integration.dispatcher import Dispatcher
from app.integration.jira_client import Issue
from app.integration.jira_sim import SimulatedJira
from app.main import create_app
from app.persistence.tables import jira_operation, review_decision, simulated_issue
from app.services.review import decide

Run = Callable[[Coroutine[Any, Any, None]], None]
SITE = "https://demo.atlassian.net"
PREFIX = SITE + "/rest/api/3"
DRAFT = {
    "vendor_name": "Synthetic Supplier",
    "service_category": "consulting",
    "business_criticality": "low",
    "sensitive_data_access": False,
    "service_description": "Synthetic service",
    "requester_department": "Examples",
    "evidence": [{"kind": "business_registration", "present": True}],
}
INFO = {"key": "VF-123", "id": "123"}


async def waiting(http: httpx.AsyncClient) -> tuple[str, dict[str, Any]]:
    r = await http.post("/api/requests", json=DRAFT)
    assert r.status_code == 201
    row = r.json()
    path = "/api/requests/" + row["id"]
    r = await http.post(path + "/submit", json={"expected_version": row["version"]})
    assert r.status_code == 202
    result = (await http.get(path)).json()
    assert result["status"] == "AWAITING_APPROVAL"
    return path, result


def human(row: dict[str, Any], action: str = "approve") -> dict[str, Any]:
    return {
        "expected_version": row["version"],
        "action": action,
        "reason": "Synthetic review",
        "reviewer_label": "Test reviewer",
    }


def config(tmp: Path, mode: str = "simulation") -> Settings:
    return Settings.model_validate(
        {
            "database_path": tmp / "demo.sqlite",
            "llm_api_key": None,
            "jira_mode": mode,
            "jira_base_url": SITE,
            "jira_project_key": "VF",
            "jira_issue_type": "Task",
            "jira_email": "fixture@example.invalid",
            "jira_api_token": SecretStr("offline-placeholder"),
        }
    )


@pytest.mark.parametrize(
    ("fault", "expected", "posts"),
    [
        ("201", "CREATED", 1),
        ("400", "FAILED", 1),
        ("401", "FAILED", 1),
        ("403", "FAILED", 1),
        ("404", "FAILED", 1),
        ("422", "FAILED", 1),
        ("429", "CREATED", 2),
        ("connect", "CREATED", 2),
        ("timeout", "UNCERTAIN", 1),
        ("reset", "UNCERTAIN", 1),
        ("500", "UNCERTAIN", 1),
        ("found-third", "CREATED", 1),
        ("rate-limit-long", "FAILED", 1),
        ("invalid-201", "UNCERTAIN", 1),
    ],
)
def test_vf09_delivery_matrix_vf10_sanitized(
    tmp_path: Path,
    run_async: Run,
    fault: str,
    expected: str,
    posts: int,
    caplog: pytest.LogCaptureFixture,
) -> None:
    app = create_app(config(tmp_path, "live"))

    async def run() -> None:
        async with (
            app.router.lifespan_context(app),
            httpx.AsyncClient(
                transport=httpx.ASGITransport(app=app), base_url="http://test"
            ) as http,
        ):
            delays: list[float] = []
            app.state.dispatcher.sleep = delays.append
            path, row = await waiting(http)
            marker = "vf-" + row["id"]
            with respx.mock(assert_all_called=False) as mock:
                metadata = mock.get(PREFIX + "/issue/createmeta/VF/issuetypes").respond(
                    200,
                    json={"issueTypes": [{"id": "100", "name": "Task"}], "total": 1},
                )
                attempts: list[dict[str, Any]] = []

                def create(request: httpx.Request) -> httpx.Response:
                    with app.state.engine.connect() as conn:
                        assert (
                            conn.scalar(
                                select(review_decision.c.action).filter_by(
                                    request_id=row["id"]
                                )
                            )
                            == "approve"
                        )
                    fields = json.loads(request.content)["fields"]
                    attempts.append(fields)
                    assert fields["labels"] == [marker] and fields["issuetype"] == {
                        "id": "100"
                    }
                    assert (
                        fields["description"]["type"] == "doc"
                        and fields["description"]["version"] == 1
                    )
                    assert (
                        row["id"]
                        in fields["description"]["content"][0]["content"][0]["text"]
                    )
                    if len(attempts) == 1:
                        if fault in {"400", "401", "403", "404", "422", "500"}:
                            return httpx.Response(
                                int(fault), text="offline-placeholder"
                            )
                        if fault in {"429", "rate-limit-long"}:
                            return httpx.Response(
                                429,
                                headers={
                                    "Retry-After": "4" if fault == "429" else "120"
                                },
                            )
                        if fault == "connect":
                            raise httpx.ConnectError("offline-placeholder")
                        if fault in {"timeout", "found-third"}:
                            raise httpx.ReadTimeout("offline-placeholder")
                        if fault == "reset":
                            raise httpx.ReadError("offline-placeholder")
                        if fault == "invalid-201":
                            return httpx.Response(201, json={"unexpected": True})
                    return httpx.Response(201, json=INFO)

                create_route = mock.post(PREFIX + "/issue").mock(side_effect=create)
                searches: list[str] = []

                def search(request: httpx.Request) -> httpx.Response:
                    searches.append(json.loads(request.content)["jql"])
                    assert searches[-1] == f'labels = "{marker}"'
                    items = (
                        [INFO | {"fields": {"labels": [marker]}}]
                        if fault == "found-third" and len(searches) == 3
                        else []
                    )
                    return httpx.Response(200, json={"issues": items})

                mock.post(PREFIX + "/search/jql").mock(side_effect=search)
                app.state.dispatcher.dispatch(UUID(row["id"]))
                assert not create_route.called and not metadata.called
                decision = await http.post(path + "/decision", json=human(row))
                assert (
                    decision.status_code == 200
                    and decision.json()["status"] == "JIRA_PENDING"
                )
                final = (await http.get(path)).json()
                op = final["jira"]
                assert (
                    op["status"] == expected
                    and op["attempts"] == posts
                    and create_route.call_count == posts
                )
                assert metadata.call_count == 1
                assert final["status"] == (
                    "JIRA_CREATED" if expected == "CREATED" else "JIRA_FAILED"
                )
                assert op["issue_url"] == (
                    SITE + "/browse/VF-123" if expected == "CREATED" else None
                )
                if fault == "found-third":
                    assert delays == [2, 5, 15]
                if expected == "UNCERTAIN":
                    assert delays == [2, 5, 15, 30]
                if fault in {"429", "connect"}:
                    assert len(searches) == 1 and delays == (
                        [4] if fault == "429" else [1]
                    )
                if fault == "rate-limit-long":
                    assert op["retry_at"]
                    assert (
                        await http.post(
                            path + "/jira/reconcile",
                            json={
                                "expected_version": final["version"],
                                "reviewer_label": "Review",
                            },
                        )
                    ).status_code == 409
                assert (
                    "offline-placeholder"
                    not in json.dumps(final)
                    + (await http.get(path + "/audit")).text
                    + caplog.text
                )

    run_async(run())


def test_vf07_simulated_reconciliation_and_confirmation(
    tmp_path: Path, run_async: Run
) -> None:
    cfg = config(tmp_path)
    app = create_app(cfg)

    async def run() -> None:
        async with (
            app.router.lifespan_context(app),
            httpx.AsyncClient(
                transport=httpx.ASGITransport(app=app), base_url="http://test"
            ) as http,
        ):
            disp = app.state.dispatcher
            disp.sleep = lambda _: None
            disp.clients["simulation"].faults.append("timeout")
            path, row = await waiting(http)
            approved = await http.post(path + "/decision", json=human(row))
            assert approved.status_code == 200
            unknown = (await http.get(path)).json()
            assert unknown["jira"]["status"] == "UNCERTAIN"
            url = path + "/jira/reconcile"
            body = {
                "expected_version": unknown["version"],
                "reviewer_label": "Demo reviewer",
            }
            check = await http.post(url, json=body)
            assert check.status_code == 202
            still = (await http.get(path)).json()
            assert (
                still["jira"]["status"] == "UNCERTAIN"
                and still["jira"]["attempts"] == 1
            )
            assert (
                await http.post(
                    url, json=body | {"checked_jira_and_no_issue_exists": True}
                )
            ).status_code == 409
            ok = await http.post(
                url,
                json=body
                | {
                    "expected_version": still["version"],
                    "checked_jira_and_no_issue_exists": True,
                },
            )
            assert ok.status_code == 202
            end = (await http.get(path)).json()
            assert (
                end["jira"]["issue_key"] == "SIM-1" and end["jira"]["issue_url"] is None
            )
            events = (await http.get(path + "/audit")).json()
            assert (
                len(
                    [
                        e
                        for e in events
                        if e["detail"].get("checked_jira_and_no_issue_exists") is True
                    ]
                )
                == 1
            )
            assert end["jira"]["attempts"] == 2

    run_async(run())


def test_vf09_crash_after_remote_create_reconcile_after_restart(
    tmp_path: Path, run_async: Run
) -> None:
    cfg = config(tmp_path)
    app = create_app(cfg)

    async def run() -> None:
        async with (
            app.router.lifespan_context(app),
            httpx.AsyncClient(
                transport=httpx.ASGITransport(app=app), base_url="http://test"
            ) as http,
        ):
            path, row = await waiting(http)
            key = UUID(row["id"])
            decide(
                app.state.engine,
                key,
                HumanDecision.model_validate(human(row)),
                "simulation",
            )
            disp: Dispatcher = app.state.dispatcher

            class CrashAfterCreate(SimulatedJira):
                def create(self, request: RequestView) -> Issue:
                    super().create(request)
                    raise SystemExit(
                        "Simulated process stop after external persistence"
                    )

            disp.clients["simulation"] = CrashAfterCreate(app.state.engine)
            with pytest.raises(SystemExit):
                disp.dispatch(key)
        second = create_app(cfg)
        async with (
            second.router.lifespan_context(second),
            httpx.AsyncClient(
                transport=httpx.ASGITransport(app=second), base_url="http://test"
            ) as http,
        ):
            current = (await http.get(path)).json()
            assert (
                current["jira"]["status"] == "UNCERTAIN"
                and current["jira"]["attempts"] == 1
            )
            response = await http.post(
                path + "/jira/reconcile",
                json={
                    "expected_version": current["version"],
                    "reviewer_label": "Reviewer",
                },
            )
            assert response.status_code == 202
            final = (await http.get(path)).json()
            assert final["jira"]["issue_key"] == "SIM-1"
            with second.state.engine.connect() as conn:
                assert (
                    conn.scalar(select(func.count()).select_from(simulated_issue)) == 1
                )
                assert (
                    conn.scalar(select(func.count()).select_from(jira_operation)) == 1
                )

    run_async(run())


@pytest.mark.parametrize(
    "site",
    [
        "http://demo.atlassian.net",
        "https://demo.atlassian.net.example.invalid",
        "https://demo.atlassian.net:444",
        "https://demo.atlassian.net/path",
        "https://user@demo.atlassian.net",
    ],
)
def test_vf10_restrict_site(site: str) -> None:
    with pytest.raises(ValidationError):
        Settings(jira_base_url=site)
