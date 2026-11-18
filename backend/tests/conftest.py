"""Create asyncio's internal wakeup pair before pytest-socket guards test code."""

import asyncio
from collections.abc import Callable, Coroutine
from typing import Any, TypeVar

import pytest

T = TypeVar("T")
RUNNER = pytest.StashKey[asyncio.Runner]()


def pytest_sessionstart(session: pytest.Session) -> None:
    runner = asyncio.Runner()
    runner.get_loop()
    session.config.stash[RUNNER] = runner


def pytest_sessionfinish(session: pytest.Session) -> None:
    session.config.stash[RUNNER].close()


@pytest.fixture
def run_async(pytestconfig: pytest.Config) -> Callable[[Coroutine[Any, Any, T]], T]:
    return pytestconfig.stash[RUNNER].run
