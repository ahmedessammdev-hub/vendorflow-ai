from uuid import UUID

from fastapi import APIRouter, BackgroundTasks, Request

from app.agents.schemas import HumanDecision
from app.domain.models import ConflictView, RequestView
from app.services.review import decide

router = APIRouter(tags=["review"])


@router.post(
    "/requests/{request_id}/decision", responses={409: {"model": ConflictView}}
)
def record_decision(
    request_id: UUID, body: HumanDecision, request: Request, background: BackgroundTasks
) -> RequestView:
    result = decide(
        request.app.state.engine, request_id, body, request.app.state.settings.jira_mode
    )
    background.add_task(request.app.state.workflow.drive, request_id)
    if body.action == "approve":
        background.add_task(request.app.state.dispatcher.dispatch, request_id)
    return result
