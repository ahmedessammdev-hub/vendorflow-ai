from collections.abc import AsyncIterator
from contextlib import ExitStack, asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from starlette.concurrency import run_in_threadpool

from app.agents.graph import build_graph
from app.agents.llm_adapter import CompatibleProvider, Provider
from app.agents.nodes import ReviewNodes
from app.api import audit, health, jira, metrics, requests, review, settings
from app.core.config import Settings
from app.core.limits import BodyLimit
from app.core.logging import RequestLog
from app.integration.dispatcher import Dispatcher
from app.integration.jira_client import JiraClient, LiveJira
from app.integration.jira_sim import SimulatedJira
from app.persistence.checkpointer import open_checkpointer
from app.persistence.database import make_engine, migrate
from app.persistence.repositories import Conflict, MissingRequest
from app.services.recovery import ReviewWorkflow


def create_app(
    config: Settings | None = None, *, provider: Provider | None = None
) -> FastAPI:
    config = config if config is not None else Settings()
    engine = make_engine(config.database_path)

    @asynccontextmanager
    async def lifespan(application: FastAPI) -> AsyncIterator[None]:
        try:
            migrate(engine)
            with ExitStack() as stack:
                active_provider = provider
                if active_provider is None and config.llm_configured:
                    live = CompatibleProvider(config)
                    stack.callback(live.client.close)
                    active_provider = live
                saver = stack.enter_context(open_checkpointer(config.checkpoint_path))
                nodes = ReviewNodes(
                    engine,
                    active_provider,
                    config.llm_api_key.get_secret_value()
                    if config.llm_api_key
                    else None,
                )
                application.state.workflow = ReviewWorkflow(
                    engine, build_graph(nodes, saver)
                )
                await run_in_threadpool(application.state.workflow.recover)
                clients: dict[str, JiraClient] = {"simulation": SimulatedJira(engine)}
                if config.jira_mode == "live":
                    live_jira = LiveJira(config)
                    stack.callback(live_jira.http.close)
                    clients["live"] = live_jira
                dispatcher = Dispatcher(engine, clients)
                application.state.dispatcher = dispatcher
                await run_in_threadpool(dispatcher.recover)
                yield
        finally:
            engine.dispose()

    application = FastAPI(title="VendorFlow AI", version="0.1.0", lifespan=lifespan)
    application.state.settings = config
    application.state.engine = engine
    application.add_middleware(BodyLimit)
    application.add_middleware(RequestLog, settings=config)
    application.add_middleware(
        CORSMiddleware,
        allow_origins=["http://localhost:4200"],
        allow_methods=["GET", "POST", "PATCH"],
        allow_headers=["Content-Type"],
    )

    @application.exception_handler(Conflict)
    async def conflict(request: Request, exc: Conflict) -> JSONResponse:
        return JSONResponse(
            {"detail": str(exc), "current": exc.current.model_dump(mode="json")},
            status_code=409,
        )

    @application.exception_handler(MissingRequest)
    async def missing(request: Request, exc: MissingRequest) -> JSONResponse:
        return JSONResponse({"detail": "Request not found."}, status_code=404)

    @application.exception_handler(RequestValidationError)
    async def invalid(request: Request, exc: RequestValidationError) -> JSONResponse:
        errors = [{k: e[k] for k in ("loc", "type", "msg")} for e in exc.errors()]
        return JSONResponse({"detail": errors}, status_code=422)

    for router in (
        health.router,
        metrics.router,
        settings.router,
        requests.router,
        audit.router,
        review.router,
        jira.router,
    ):
        application.include_router(router, prefix="/api")
    return application


app = create_app()
