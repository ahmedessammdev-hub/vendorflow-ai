import json
from pathlib import Path

import httpx2
import pytest
from openai import DefaultHttpxClient
from pydantic import SecretStr

from app.agents.llm_adapter import CompatibleProvider, ProviderDown, SchemaUnsupported
from app.agents.schemas import IntakeSummary
from app.core.config import Settings


@pytest.mark.parametrize("custom_options", [False, True])
def test_vf04_sdk_contract_and_fallback(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, custom_options: bool
) -> None:
    for name in ("LLM_TIMEOUT_SECONDS", "LLM_REASONING_EFFORT", "LLM_MAX_TOKENS"):
        monkeypatch.delenv(name, raising=False)
    config = Settings(
        _env_file=None,
        database_path=tmp_path / "test.sqlite",
        llm_api_key=SecretStr("offline-placeholder"),
        llm_model="configured-alias",
        llm_base_url="https://fixture.invalid/v1",
    )
    if custom_options:
        config = config.model_copy(
            update={
                "llm_timeout_seconds": 120.0,
                "llm_reasoning_effort": "low",
                "llm_max_tokens": 4096,
            }
        )
    adapter = CompatibleProvider(config)
    messages: list[dict[str, object]] = []

    def respond(request: httpx2.Request) -> httpx2.Response:
        assert request.url.path == "/v1/chat/completions"
        data = json.loads(request.read())
        assert data["temperature"] == 0 and "tools" not in data
        assert request.extensions["timeout"]["read"] == (
            120.0 if custom_options else 30.0
        )
        if custom_options:
            assert data["reasoning_effort"] == "low" and data["max_tokens"] == 4096
        else:
            assert "reasoning_effort" not in data and "max_tokens" not in data
        messages.append(data)
        if len(messages) == 1:
            assert data["response_format"]["json_schema"]["strict"]
            return httpx2.Response(
                400,
                json={"error": {"message": "unsupported response_format json_schema"}},
            )
        if len(messages) == 2:
            assert data["response_format"] == {"type": "json_object"}
            return httpx2.Response(
                200,
                json={
                    "object": "chat.completion",
                    "id": "fixture",
                    "created": 1,
                    "model": "fixture-revision",
                    "choices": [
                        {
                            "index": 0,
                            "message": {"role": "assistant", "content": "{}"},
                            "finish_reason": "stop",
                        }
                    ],
                    "usage": {
                        "prompt_tokens": 4,
                        "completion_tokens": 2,
                        "total_tokens": 6,
                    },
                },
            )
        return httpx2.Response(503, json={"error": {"message": "unavailable"}})

    with (
        adapter.client as sdk,
        DefaultHttpxClient(transport=httpx2.MockTransport(respond)) as offline,
    ):
        adapter.client = sdk.with_options(http_client=offline)
        with pytest.raises(SchemaUnsupported):
            adapter.complete(IntakeSummary, "system", "data", False)
        got = adapter.complete(IntakeSummary, "system", "data", True)
        assert (got.model, got.content, got.tokens_in, got.tokens_out) == (
            "fixture-revision",
            "{}",
            4,
            2,
        )
        with pytest.raises(ProviderDown, match="^http_503$"):
            adapter.complete(IntakeSummary, "system", "data", True)
    assert len(messages) == 3


@pytest.mark.parametrize(
    ("failure", "category"),
    [
        ("timeout", "timeout"),
        ("connection", "connection_error"),
        ("limited", "http_429"),
    ],
)
def test_transport_diagnostics_exclude_response_and_exception_text(
    failure: str, category: str
) -> None:
    adapter = CompatibleProvider(
        Settings(
            _env_file=None,
            llm_api_key=SecretStr("fixture-only"),
            llm_model="offline",
            llm_base_url="https://fixture.invalid/v1",
        )
    )

    def respond(request: httpx2.Request) -> httpx2.Response:
        if failure == "timeout":
            raise httpx2.ReadTimeout("private detail", request=request)
        if failure == "connection":
            raise httpx2.ConnectError("private detail", request=request)
        return httpx2.Response(429, json={"error": {"message": "private detail"}})

    with (
        adapter.client as sdk,
        DefaultHttpxClient(transport=httpx2.MockTransport(respond)) as offline,
    ):
        adapter.client = sdk.with_options(http_client=offline)
        with pytest.raises(ProviderDown) as caught:
            adapter.complete(IntakeSummary, "system", "data", True)
    assert caught.value.category == str(caught.value) == category
    assert ProviderDown("private detail").category == "provider_error"
