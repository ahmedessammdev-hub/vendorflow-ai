from uuid import UUID

from fastapi import APIRouter, BackgroundTasks, Request

from app.agents.schemas import Reconcile
from app.domain.models import ConflictView, RequestView
from app.integration.dispatcher import Dispatcher
from app.persistence import repositories as repo
from app.services.requests import RequestService

router = APIRouter(tags=["jira"])


@router.post(
    "/requests/{request_id}/jira/reconcile",
    status_code=202,
    responses={409: {"model": ConflictView}},
)
def reconcile(
    request_id: UUID, body: Reconcile, request: Request, background: BackgroundTasks
) -> RequestView:
    dispatcher: Dispatcher = request.app.state.dispatcher
    claim = dispatcher.claim(request_id, body)
    if claim is None:
        raise repo.Conflict(
            "Another worker claimed the operation.",
            RequestService(dispatcher.engine).get(request_id),
        )
    background.add_task(dispatcher.deliver, claim)
    return claim.request
