import logging
from collections.abc import Callable, MutableMapping
from typing import Any
from uuid import uuid4

import structlog
from starlette.datastructures import MutableHeaders
from starlette.types import ASGIApp, Message, Receive, Scope, Send

from app.core.config import Settings


def redactor(
    settings: Settings,
) -> Callable[[Any, str, MutableMapping[str, Any]], dict[str, Any]]:
    secrets = [
        s.get_secret_value()
        for s in (settings.llm_api_key, settings.jira_api_token)
        if s and s.get_secret_value()
    ]

    def clean(value: Any) -> Any:
        if isinstance(value, MutableMapping):
            return {
                k: "[REDACTED]"
                if any(
                    name in k.lower()
                    for name in ("authorization", "api_key", "token", "password")
                )
                else clean(v)
                for k, v in value.items()
            }
        if isinstance(value, (tuple, list)):
            return [clean(v) for v in value]
        if isinstance(value, str):
            for secret in secrets:
                value = value.replace(secret, "[REDACTED]")
        return value

    def process(_: Any, method: str, event: MutableMapping[str, Any]) -> dict[str, Any]:
        return {k: v for k, v in clean(event).items()}

    return process


class RequestLog:
    def __init__(self, app: ASGIApp, settings: Settings) -> None:
        self.app = app
        self.log = structlog.wrap_logger(
            logging.getLogger("vendorflow.requests"),
            processors=[redactor(settings), structlog.processors.JSONRenderer()],
        )

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        correlation = uuid4().hex

        async def respond(message: Message) -> None:
            if message["type"] == "http.response.start":
                MutableHeaders(scope=message)["X-Request-ID"] = correlation
                self.log.info(
                    "request",
                    request_id=correlation,
                    method=scope["method"],
                    status=message["status"],
                )
            await send(message)

        await self.app(scope, receive, respond)
