"""Create asyncio's internal wakeup pair before pytest-socket guards test code."""

import asyncio
from collections.abc import Callable, Coroutine
from typing import Any, TypeVar

import pytest
from sqlalchemy import Engine, select

from app import main
from app.core.config import Settings
from app.domain.models import RequestView
from app.integration.jira_client import Issue, LiveJira
from app.integration.jira_sim import SimulatedJira
from app.persistence.database import make_engine
from app.persistence.tables import review_decision

T = TypeVar("T")
RUNNER = pytest.StashKey[asyncio.Runner]()
PREAPPROVAL_CALLS = pytest.StashKey[int]()


def pytest_sessionstart(session: pytest.Session) -> None:
    session.config.stash[PREAPPROVAL_CALLS] = 0
    runner = asyncio.Runner()
    runner.get_loop()
    session.config.stash[RUNNER] = runner


def pytest_sessionfinish(session: pytest.Session) -> None:
    session.config.stash[RUNNER].close()


@pytest.fixture
def run_async(pytestconfig: pytest.Config) -> Callable[[Coroutine[Any, Any, T]], T]:
    return pytestconfig.stash[RUNNER].run


@pytest.fixture(autouse=True)
def guard_jira_creates(
    monkeypatch: pytest.MonkeyPatch, pytestconfig: pytest.Config
) -> None:
    monkeypatch.setenv("JIRA_MODE", "simulation")
    monkeypatch.setenv("LLM_API_KEY", "")
    monkeypatch.setenv("JIRA_API_TOKEN", "")

    def check(engine: Engine, request: RequestView) -> None:
        with engine.connect() as conn:
            approved = conn.scalar(
                select(review_decision.c.id).filter_by(
                    request_id=str(request.id), action="approve"
                )
            )
        if approved is None:
            pytestconfig.stash[PREAPPROVAL_CALLS] += 1
            pytest.fail("Jira create attempted before persisted approval")

    simulated_create = SimulatedJira.create

    def checked_simulation(client: SimulatedJira, request: RequestView) -> Issue:
        check(client.engine, request)
        return simulated_create(client, request)

    class CheckedLiveJira(LiveJira):
        def __init__(self, settings: Settings) -> None:
            super().__init__(settings)
            self.database_path = settings.database_path

        def create(self, request: RequestView) -> Issue:
            engine = make_engine(self.database_path)
            try:
                check(engine, request)
            finally:
                engine.dispose()
            return super().create(request)

    monkeypatch.setattr(SimulatedJira, "create", checked_simulation)
    monkeypatch.setattr(main, "LiveJira", CheckedLiveJira)


def pytest_terminal_summary(terminalreporter: Any, config: pytest.Config) -> None:
    terminalreporter.write_line(
        f"Jira creates before persisted approval: {config.stash[PREAPPROVAL_CALLS]}"
    )
