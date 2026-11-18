from collections.abc import Callable, Coroutine
from typing import Any

import httpx
import pytest
from pydantic import SecretStr

from app.core.config import Settings
from app.main import create_app

RunRequest = Callable[[Coroutine[Any, Any, httpx.Response]], httpx.Response]


async def get_response(config: Settings, path: str) -> httpx.Response:
    transport = httpx.ASGITransport(app=create_app(config))
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        return await client.get(path)


@pytest.mark.parametrize("path", ["/api/health", "/api/settings/integrations"])
def test_vf11_modes_without_credentials(path: str, run_async: RunRequest) -> None:
    config = Settings(
        llm_api_key=None, llm_base_url="", llm_model="", jira_mode="simulation"
    )
    response = run_async(get_response(config, path))
    assert response.status_code == 200
    expected = {
        "authentication": "none",
        "llm_mode": "unavailable",
        "jira_mode": "simulation",
    }
    if path.endswith("/health"):
        expected["status"] = "ok"
    assert response.json() == expected


def test_vf10_configured_modes_expose_only_public_fields(run_async: RunRequest) -> None:
    config = Settings(
        llm_api_key=SecretStr("unit-test-placeholder"),
        llm_base_url="https://example.invalid",
        llm_model="unit-test-model",
        jira_mode="live",
    )
    response = run_async(get_response(config, "/api/settings/integrations"))
    assert response.status_code == 200
    assert response.json() == {
        "authentication": "none",
        "llm_mode": "configured",
        "jira_mode": "live",
    }
