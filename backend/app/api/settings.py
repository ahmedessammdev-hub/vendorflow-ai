from typing import Literal

from fastapi import APIRouter, Request
from pydantic import BaseModel

from app.core.config import Settings

router = APIRouter()


class IntegrationModes(BaseModel):
    authentication: Literal["none"] = "none"
    llm_mode: Literal["unavailable", "configured"]
    jira_mode: Literal["simulation", "live"]


def integration_modes(settings: Settings) -> IntegrationModes:
    return IntegrationModes(
        llm_mode="configured" if settings.llm_configured else "unavailable",
        jira_mode=settings.jira_mode,
    )


@router.get("/settings/integrations")
def get_integrations(request: Request) -> IntegrationModes:
    return integration_modes(request.app.state.settings)
