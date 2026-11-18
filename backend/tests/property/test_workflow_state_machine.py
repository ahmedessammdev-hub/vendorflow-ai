from collections.abc import Callable, Coroutine
from pathlib import Path
from typing import Any
from uuid import UUID

import httpx
from hypothesis import HealthCheck, settings
from hypothesis import strategies as st
from hypothesis.stateful import (
    RuleBasedStateMachine,
    invariant,
    rule,
    run_state_machine_as_test,
)
from sqlalchemy import func, select

from app.core.config import Settings
from app.domain.enums import Status
from app.domain.transitions import apply
from app.main import create_app
from app.persistence.tables import jira_operation, review_decision, simulated_issue


def test_vf05_vf09_vf10_random_action_sequences(
    tmp_path: Path, run_async: Callable[[Coroutine[Any, Any, Any]], Any]
) -> None:
    app = create_app(
        Settings(
            database_path=tmp_path / "property.sqlite",
            llm_api_key=None,
            jira_mode="simulation",
        )
    )
    http = httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test"
    )
    lifespan = app.router.lifespan_context(app)
    run_async(lifespan.__aenter__())

    class Workflow(RuleBasedStateMachine):
        def __init__(self) -> None:
            super().__init__()
            draft = run_async(
                http.post(
                    "/api/requests",
                    json={
                        "vendor_name": "State machine supplier",
                        "service_category": "consulting",
                        "business_criticality": "low",
                        "sensitive_data_access": False,
                        "service_description": "Synthetic work",
                        "requester_department": "Testing",
                        "evidence": [
                            {"kind": "business_registration", "present": True}
                        ],
                    },
                )
            )
            assert draft.status_code == 201
            self.key = draft.json()["id"]
            self.path = "/api/requests/" + self.key
            self.events: list[dict[str, Any]] = []

        def current(self) -> dict[str, Any]:
            return dict(run_async(http.get(self.path)).json())

        @rule()
        def submit(self) -> None:
            row = self.current()
            r = run_async(
                http.post(
                    self.path + "/submit", json={"expected_version": row["version"]}
                )
            )
            assert r.status_code in (200, 202, 409)

        @rule(
            action=st.sampled_from(["approve", "reject", "request_changes"]),
            stale=st.booleans(),
        )
        def decide(self, action: str, stale: bool) -> None:
            row = self.current()
            r = run_async(
                http.post(
                    self.path + "/decision",
                    json={
                        "expected_version": row["version"] + int(stale),
                        "reviewer_label": "Fixture",
                        "reason": "Synthetic review",
                        "action": action,
                    },
                )
            )
            assert r.status_code == (
                200 if row["status"] == "AWAITING_APPROVAL" and not stale else 409
            )

        @rule(present=st.booleans())
        def edit(self, present: bool) -> None:
            row = self.current()
            r = run_async(
                http.patch(
                    self.path,
                    json={
                        "expected_version": row["version"],
                        "evidence": [
                            {"kind": "business_registration", "present": present}
                        ],
                    },
                )
            )
            assert r.status_code == (
                200 if row["status"] in {"DRAFT", "NEEDS_CHANGES"} else 409
            )

        @rule()
        def dispatch_again(self) -> None:
            app.state.dispatcher.dispatch(UUID(self.key))

        @invariant()
        def immutable_history_and_single_authorized_operation(self) -> None:
            log = run_async(http.get(self.path + "/audit")).json()
            assert log[: len(self.events)] == self.events
            previous = self.events[-1]["to_status"] if self.events else None
            for event in log[len(self.events) :]:
                assert event["from_status"] == previous
                target = Status(event["to_status"])
                if event["event_type"] == "edited":
                    assert target == previous
                else:
                    assert (
                        apply(Status(previous) if previous else None, target) == target
                    )
                previous = target
            self.events = log
            assert self.current()["status"] == previous
            with app.state.engine.connect() as conn:
                approved = conn.scalar(
                    select(func.count())
                    .select_from(review_decision)
                    .filter_by(request_id=self.key, action="approve")
                )
                operations = conn.scalar(
                    select(func.count())
                    .select_from(jira_operation)
                    .filter_by(request_id=self.key)
                )
                created = conn.scalar(
                    select(func.count())
                    .select_from(simulated_issue)
                    .filter_by(marker="vf-" + self.key)
                )
                assert created == operations == approved and created in (0, 1)

    try:
        run_state_machine_as_test(
            Workflow,
            settings=settings(
                max_examples=500,
                stateful_step_count=7,
                deadline=None,
                suppress_health_check=[HealthCheck.too_slow],
            ),
        )
    finally:
        run_async(http.aclose())
        run_async(lifespan.__aexit__(None, None, None))
